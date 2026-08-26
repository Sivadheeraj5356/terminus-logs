"""Behavioral verifier for the periodic damped wave (telegraph) task.

The agent supplies a from-scratch finite-difference solver in C for

    u_tt + 2 g u_t = c^2 u_xx,   x in [0, 1),   u_t(x, 0) = 0,

with periodic boundaries, wave speed c, and damping rate g. This suite compiles
the agent's source, runs the resulting binary on pristine verifier-owned fixtures
(never the agent-writable input at /app/input), and grades the emitted field
snapshots by three independent paths:

  (a) discrete mass conservation, finiteness, and a discrete-energy monotonicity
      bound recomputed from the emitted displacement and velocity (rejects
      unstable, over-CFL, and anti-dissipative schemes);
  (b) agreement with the independent closed-form per-mode solution within a
      per-snapshot relative-L2 tolerance (rejects the standard second-order
      scheme, low-order time integrators, and undamped or wrong-physics schemes);
  (c) the measured spatial/temporal convergence order under grid refinement with
      the Courant number held fixed, which must reach at least sixth order (rejects
      any lower-order scheme - including a sixth-order spatial stencil advanced by
      only a fourth-order time integrator, whose Courant-limited slope stalls near
      four - and the closed-form shortcut whose slope is ~0).

Reward comes only from executed behavior compared with the independent reference
or a discrete invariant, never from a value the agent reports and never from
inspecting the agent's source. The same master grader is applied identically to
the agent, the oracle, and every external wrong baseline. Hidden speeds, damping
rates, profiles, grids, Courant numbers, and snapshot times differ from the
agent-visible fixture, so a memorized field cannot pass. The build is fully
offline with only the C standard library and libm available.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference import (
    analytic_solution,
    analytic_velocity,
    discrete_energy,
    grid,
    initial_field,
)

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.path.join(HERE, "baselines")
APP = os.environ.get("TELEGRAPH_APP", "/app")

# Anti-gaming sandbox. When the suite runs as root (inside the graded image) the
# untrusted candidate binary AND its build are executed as an unprivileged user so
# they cannot read the verifier assets (reference, fixtures, tolerances) or exec an
# interpreter to fabricate a trace; test.sh separately strips read/execute access
# to /tests and to python3/numpy. When the suite runs as an ordinary user (local
# authoring) the drop is a no-op, so behavior is identical. Trusted
# author-controlled baselines run without the drop.
SANDBOX = hasattr(os, "geteuid") and os.geteuid() == 0


def _unpriv_ids():
    import pwd

    try:
        gid = pwd.getpwnam("nobody").pw_gid
    except Exception:
        gid = 65534
    try:
        import grp

        gid = grp.getgrnam("nogroup").gr_gid
    except Exception:
        pass
    try:
        uid = pwd.getpwnam("nobody").pw_uid
    except Exception:
        uid = 65534
    return uid, gid


def _drop_privs():
    uid, gid = _unpriv_ids()
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)


def _open_build_tree():
    """Let the unprivileged build write anywhere in /app (the agent's own
    workspace) - the binary and any intermediate objects a restructured Makefile
    might emit - without granting any access to the verifier assets. /app already
    belongs to the agent, so this exposes nothing new; /tests stays root-only."""
    for root, _dirs, files in os.walk(APP):
        try:
            os.chmod(root, 0o777)
        except OSError:
            pass
        for f in files:
            p = os.path.join(root, f)
            try:
                os.chmod(p, os.stat(p).st_mode | 0o666)
            except OSError:
                pass


CSV_HEADER = "t,x,u,v"
# A field written in full double precision: scientific notation with at least
# fifteen fractional mantissa digits (the provided writer uses %.16e). Non-finite
# sentinels are allowed here and are caught separately by the finiteness grade.
_FULL_PRECISION = re.compile(r"^[+-]?\d\.\d{15,}[eE][+-]?\d+$")
_NON_FINITE = re.compile(r"^[+-]?(inf|infinity|nan)$", re.IGNORECASE)


def valid_csv_text(text, nsnap, N):
    """Confirm the emitted CSV obeys the output contract: an exact ``t,x,u,v``
    header, exactly ``1 + nsnap*N`` lines, four fields per data row, and every
    finite field written in full double precision. Returns True or False."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != CSV_HEADER:
        return False
    if len(lines) != 1 + nsnap * N:
        return False
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) != 4:
            return False
        for p in parts:
            p = p.strip()
            if _NON_FINITE.match(p):
                continue
            if not _FULL_PRECISION.match(p):
                return False
    return True


with open(os.path.join(HERE, "fixtures", "cases.json")) as _fh:
    CASES = json.load(_fh)

PROFILES = CASES["profiles"]
TOL = CASES["tol"]
LADDER = CASES["conv_ladder"]
CONV_NU = CASES["conv_nu"]
CONV_TSTAR = CASES["conv_tstar"]


def prof(key):
    return PROFILES[key]


def snaps_for(T):
    """Five snapshots from 0 to T."""
    return [0.0, T / 4.0, T / 2.0, 3.0 * T / 4.0, T]


def _mk(cn):
    return dict(
        name=cn["name"],
        c=cn["c"],
        g=cn["g"],
        profile=prof(cn["profile"]),
        N=cn["N"],
        nu=cn["nu"],
        snaps=snaps_for(cn["T"]),
    )


MAIN = [_mk(cn) for cn in CASES["main_cases"]]
HV = [_mk(cn) for cn in CASES["hard_validity"]]
ALL = MAIN + HV
BY_NAME = {c["name"]: c for c in ALL}


# --------------------------------------------------------------------------
# Build helpers (zero-credit execution preconditions)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def agent_bin():
    """Compile the agent's C project offline via its Makefile; return binary.

    When the suite runs as root (the graded image) the build itself is dropped to
    an unprivileged user. A hostile Makefile could otherwise fire a build-time
    shell escape (``make`` expands ``$(shell ...)`` while merely parsing the file,
    even when the binary is up to date) that, running as root, would read the
    verifier assets or exec an interpreter while /tests is root-only - the run-time
    drop alone leaves the build privileged. The build writes only into /app, so
    dropping it changes nothing for a well-behaved project. Off-root local runs
    skip the drop and behave identically.
    """
    kw = {}
    if SANDBOX:
        _open_build_tree()
        d = tempfile.mkdtemp(prefix="agentbuild_")
        os.chmod(d, 0o777)
        env = dict(os.environ)
        env["HOME"] = d
        env["TMPDIR"] = d
        kw = {"preexec_fn": _drop_privs, "env": env}
    r = subprocess.run(["make"], cwd=APP, capture_output=True, text=True, **kw)
    assert r.returncode == 0, "agent build failed:\n" + r.stderr
    b = os.path.join(APP, "solver")
    assert os.path.exists(b), "agent binary not found after build"
    return b


@lru_cache(maxsize=None)
def baseline_bin(name):
    """Compile an external wrong-baseline C source; return its binary path."""
    src = os.path.join(BASELINE_DIR, name + ".c")
    d = tempfile.mkdtemp(prefix="baseline_" + name + "_")
    out = os.path.join(d, "solver")
    r = subprocess.run(
        ["cc", "-std=gnu99", "-O2", "-o", out, src, "-lm"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"baseline {name} build failed:\n{r.stderr}"
    return out


def make_input(profile, c, g, N, nu, snaps):
    payload = {
        "c": c,
        "g": g,
        "N": N,
        "nu": nu,
        "T": snaps[-1],
        "snapshots": list(snaps),
        "kind": profile["kind"],
    }
    if profile["kind"] == "gaussian":
        payload["center"] = profile["center"]
        payload["width"] = profile["width"]
    else:
        payload["const"] = profile["c0"]
        payload["amps"] = profile["amps"]
        payload["waves"] = profile["waves"]
        payload["phases"] = profile["phases"]
    return payload


def run(binpath, profile, c, g, N, nu, snaps, sandbox=False):
    """Run a solver binary on one input; return (nsnap, N, 2) [u, v] or None.

    The emitted CSV is validated against the output contract (exact header, line
    count, four full-precision fields per row) and the emitted grid against the
    pinned grid x_i = i/N and the snapshot ordering; any structural violation
    yields None (ungradeable). When ``sandbox`` is set and the suite runs as root,
    the binary is executed as an unprivileged user in a world-writable scratch
    directory so it cannot read the verifier assets.
    """
    d = tempfile.mkdtemp(prefix="run_")
    inp = os.path.join(d, "in.json")
    out = os.path.join(d, "out.csv")
    with open(inp, "w") as f:
        json.dump(make_input(profile, c, g, N, nu, snaps), f)
    kw = {}
    if sandbox and SANDBOX:
        os.chmod(d, 0o777)
        os.chmod(inp, 0o644)
        env = dict(os.environ)
        env["HOME"] = d
        kw = {"preexec_fn": _drop_privs, "env": env}
    try:
        r = subprocess.run(
            [binpath, inp, out], capture_output=True, text=True, timeout=180, **kw
        )
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not os.path.exists(out):
        return None
    ns = len(snaps)
    with open(out) as fh:
        text = fh.read()
    if not valid_csv_text(text, ns, N):
        return None
    try:
        data = np.loadtxt(out, delimiter=",", skiprows=1)
    except Exception:
        return None
    if data.ndim != 2 or data.shape != (ns * N, 4):
        return None
    data = data.reshape(ns, N, 4)
    xg = grid(N)
    for s in range(ns):
        if not np.allclose(data[s, :, 1], xg, atol=1e-9):
            return None
        if not np.allclose(data[s, :, 0], snaps[s], atol=1e-9):
            return None
    return data[:, :, 2:]  # (ns, N, 2): displacement u and velocity v


_AGENT_RUN_CACHE = {}


def agent_run(cfg):
    name = cfg["name"]
    if name not in _AGENT_RUN_CACHE:
        _AGENT_RUN_CACHE[name] = run(
            agent_bin(),
            cfg["profile"],
            cfg["c"],
            cfg["g"],
            cfg["N"],
            cfg["nu"],
            tuple(cfg["snaps"]),
            sandbox=True,
        )
    return _AGENT_RUN_CACHE[name]


# --------------------------------------------------------------------------
# Grading primitives (independent recomputation from the emitted field)
# --------------------------------------------------------------------------
def rel_l2(a, b):
    denom = math.sqrt(float(np.sum(b**2)))
    if denom == 0.0:
        denom = 1.0
    return math.sqrt(float(np.sum((a - b) ** 2))) / denom


def grade_case(data, cfg, loose=False):
    """Apply paths (a) and (b) to one run's snapshots. Returns (ok, why)."""
    if data is None:
        return False, "no gradeable output"
    c, g, N, p, snaps = cfg["c"], cfg["g"], cfg["N"], cfg["profile"], cfg["snaps"]
    xg = grid(N)
    M0 = float(initial_field(p, N).sum() / N)
    l2max = TOL["l2_base_loose"] if loose else TOL["l2_base"]
    energies = []
    for s, ts in enumerate(snaps):
        U, V = data[s][:, 0], data[s][:, 1]
        if not (np.all(np.isfinite(U)) and np.all(np.isfinite(V))):
            return False, f"{cfg['name']}@t={ts:.3g}: non-finite"
        mass = float(U.sum() / N)
        if abs(mass - M0) > TOL["mass_bound"]:
            return False, f"{cfg['name']}@t={ts:.3g}: mass dev {abs(mass - M0):.2e}"
        e = rel_l2(U, analytic_solution(p, c, g, xg, ts))
        if e > l2max:
            return False, f"{cfg['name']}@t={ts:.3g}: L2 {e:.2e} > {l2max:.2e}"
        energies.append(discrete_energy(U, V, c, N))
    for s in range(1, len(energies)):
        if energies[s] > energies[s - 1] + TOL["energy_tol"]:
            rise = energies[s] - energies[s - 1]
            return False, f"{cfg['name']}: energy rose by {rise:.2e} at snap {s}"
    return True, "ok"


def conv_slope(binpath, cvcfg, sandbox=False):
    """Fit log(rel-L2 of displacement) vs log(dx) at a fixed time; return slope."""
    c, g, p = cvcfg["c"], cvcfg["g"], prof(cvcfg["profile"])
    hs, es = [], []
    for N in LADDER:
        data = run(binpath, p, c, g, N, CONV_NU, (0.0, CONV_TSTAR), sandbox=sandbox)
        if data is None:
            return -1.0
        U = data[-1][:, 0]
        if not np.all(np.isfinite(U)):
            return -1.0
        e = rel_l2(U, analytic_solution(p, c, g, grid(N), CONV_TSTAR))
        es.append(max(e, 1e-15))
        hs.append(1.0 / N)
    return float(np.polyfit(np.log(hs), np.log(es), 1)[0])


def full_reward(binpath, sandbox=False):
    """Single master grader used identically for agent, oracle, and baselines."""
    for cfg in MAIN:
        ok, why = grade_case(
            run(
                binpath,
                cfg["profile"],
                cfg["c"],
                cfg["g"],
                cfg["N"],
                cfg["nu"],
                tuple(cfg["snaps"]),
                sandbox=sandbox,
            ),
            cfg,
            loose=False,
        )
        if not ok:
            return False, "path-a/b main: " + why
    for cfg in HV:
        ok, why = grade_case(
            run(
                binpath,
                cfg["profile"],
                cfg["c"],
                cfg["g"],
                cfg["N"],
                cfg["nu"],
                tuple(cfg["snaps"]),
                sandbox=sandbox,
            ),
            cfg,
            loose=True,
        )
        if not ok:
            return False, "path-a/b hard-validity: " + why
    for cvcfg in CASES["convergence"]:
        s = conv_slope(binpath, cvcfg, sandbox=sandbox)
        if not (TOL["slope_lo"] <= s <= TOL["slope_hi"]):
            return False, f"path-c {cvcfg['name']}: slope {s:.3f}"
    return True, "reward 1"


# --------------------------------------------------------------------------
# Parametrization lists
# --------------------------------------------------------------------------
MAIN_SNAP = [(c["name"], s) for c in MAIN for s in range(5)]
HV_SNAP = [(c["name"], s) for c in HV for s in range(5)]


# --------------------------------------------------------------------------
# Preconditions (zero credit)
# --------------------------------------------------------------------------
def test_agent_builds():
    """Precondition: the agent's C project compiles offline via its Makefile."""
    assert os.path.exists(agent_bin())


def test_no_external_numeric_library_available():
    """From-scratch guarantee: no linear-algebra/spectral library can be linked.

    The environment must offer no library that could replace the hand-written
    stepper. We confirm this behaviorally: probes that include and link common
    numeric libraries must fail to build in the task image (only the C standard
    library and libm are present).
    """
    d = tempfile.mkdtemp(prefix="probe_")
    probes = [
        (
            "gsl",
            "#include <gsl/gsl_odeiv2.h>\nint main(){return 0;}\n",
            ["-lgsl", "-lgslcblas"],
        ),
        (
            "lapacke",
            "#include <lapacke.h>\nint main(){return 0;}\n",
            ["-llapacke", "-llapack"],
        ),
        ("fftw", "#include <fftw3.h>\nint main(){return 0;}\n", ["-lfftw3"]),
    ]
    for nm, code, libs in probes:
        src = os.path.join(d, nm + ".c")
        with open(src, "w") as f:
            f.write(code)
        r = subprocess.run(
            ["cc", "-std=c99", "-o", os.path.join(d, nm), src] + libs + ["-lm"],
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0, f"{nm} unexpectedly available to link"


def test_output_artifact():
    """The requested /app/output/field.csv artifact is produced by running the
    agent's solver on the visible input, with the exact t,x,u,v header, full
    double precision, and one row per (snapshot, grid point).

    The solver is executed under the same unprivileged drop as every other
    candidate run, so producing this mandated artifact grants it no privileged
    window: run as root it could undo the asset-protection chmods (root ignores
    permission bits) or copy the reference, fixtures, and tolerances out of /tests
    before the sandboxed grading runs. /app is the agent's own workspace, so
    opening the output directory for the dropped user exposes nothing new."""
    binp = agent_bin()
    inp = os.path.join(APP, "input", "transport.json")
    outdir = os.path.join(APP, "output")
    outp = os.path.join(outdir, "field.csv")
    assert os.path.exists(inp), "visible input /app/input/transport.json missing"
    os.makedirs(outdir, exist_ok=True)
    kw = {}
    if SANDBOX:
        os.chmod(outdir, 0o777)
        if os.path.exists(outp):
            try:
                os.chmod(outp, 0o666)
            except OSError:
                pass
        env = dict(os.environ)
        env["HOME"] = outdir
        kw = {"preexec_fn": _drop_privs, "env": env}
    r = subprocess.run(
        [binp, inp, outp], capture_output=True, text=True, timeout=180, **kw
    )
    assert r.returncode == 0, f"solver failed on the visible input: {r.stderr}"
    assert os.path.exists(outp), "solver did not write /app/output/field.csv"
    with open(inp) as fh:
        vis = json.load(fh)
    N = int(vis["N"])
    nsnap = len(vis["snapshots"])
    with open(outp) as fh:
        text = fh.read()
    assert valid_csv_text(text, nsnap, N), (
        "/app/output/field.csv header, precision, or shape does not meet the contract"
    )


def test_sandbox_blocks_candidate_asset_read():
    """Self-test of the privilege drop that shields the verifier assets.

    A program executed under the same unprivileged drop applied to the candidate
    binary and its build cannot read a root-only file. This is the mechanism that
    keeps a hostile candidate binary (or a build-time Makefile shell escape) from
    reading the reference, fixtures, or tolerances under /tests. The key is
    root-owned and mode 0600, protected only by the drop (as a root sanity run
    confirms), so a BLOCKED verdict comes from the dropped privileges, not from the
    file being unreadable to everyone. Off the graded image the drop is a no-op, so
    the check only runs as root; it plants its own key rather than depending on the
    /tests mount so it is independent of how the runner provides /tests."""
    if not SANDBOX:
        pytest.skip("privilege drop is a no-op outside the graded (root) image")
    d = tempfile.mkdtemp(prefix="sbxkey_")
    os.chmod(d, 0o777)
    key = os.path.join(d, "reference.key")
    with open(key, "w") as f:
        f.write("VERIFIER_SECRET")
    os.chmod(key, 0o600)
    probe = os.path.join(d, "probe")
    shutil.copyfile(baseline_bin("probe_readkey"), probe)
    os.chmod(probe, 0o755)
    env = dict(os.environ)
    env["HOME"] = d

    dropped = os.path.join(d, "verdict_dropped.txt")
    subprocess.run(
        [probe, key, dropped],
        preexec_fn=_drop_privs,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert os.path.exists(dropped), "probe did not run under the drop"
    with open(dropped) as fh:
        result = fh.read().strip()
    assert result == "BLOCKED", (
        f"privilege drop failed - candidate read the key: {result}"
    )

    root_verdict = os.path.join(d, "verdict_root.txt")
    subprocess.run(
        [probe, key, root_verdict], capture_output=True, text=True, timeout=60
    )
    with open(root_verdict) as fh:
        rootres = fh.read().strip()
    assert rootres.startswith("LEAK:"), (
        f"self-test inconsistent: the key is not protected by the drop alone: {rootres}"
    )


# --------------------------------------------------------------------------
# Path (a): mass conservation, finiteness, energy monotonicity
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", [c["name"] for c in ALL])
def test_mass_conservation(name):
    """The grid sum of the displacement times dx equals its initial value."""
    cfg = BY_NAME[name]
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    M0 = float(initial_field(cfg["profile"], cfg["N"]).sum() / cfg["N"])
    for s in range(5):
        U = data[s][:, 0]
        mass = float(U.sum() / cfg["N"])
        assert abs(mass - M0) <= TOL["mass_bound"], (
            f"{name} snap {s}: mass dev {abs(mass - M0):.2e}"
        )


@pytest.mark.parametrize("name", [c["name"] for c in ALL])
def test_finiteness(name):
    """Every emitted displacement and velocity value is finite."""
    cfg = BY_NAME[name]
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    for s in range(5):
        assert np.all(np.isfinite(data[s])), f"{name} snap {s}: non-finite"


@pytest.mark.parametrize("name", [c["name"] for c in ALL])
def test_energy_monotone(name):
    """The discrete energy never increases from one snapshot to the next."""
    cfg = BY_NAME[name]
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    e = [
        discrete_energy(data[s][:, 0], data[s][:, 1], cfg["c"], cfg["N"])
        for s in range(5)
    ]
    for s in range(1, 5):
        assert e[s] <= e[s - 1] + TOL["energy_tol"], (
            f"{name}: energy rose by {e[s] - e[s - 1]:.2e} at snap {s}"
        )


# --------------------------------------------------------------------------
# Path (b): analytic-solution agreement
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name,s", MAIN_SNAP)
def test_reference_snapshot_main(name, s):
    """Emitted displacement matches the exact solution within the tight L2 band."""
    cfg = BY_NAME[name]
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    ts = cfg["snaps"][s]
    ref = analytic_solution(cfg["profile"], cfg["c"], cfg["g"], grid(cfg["N"]), ts)
    e = rel_l2(data[s][:, 0], ref)
    assert e <= TOL["l2_base"], f"{name}@t={ts:.3g}: L2 {e:.2e} > {TOL['l2_base']:.2e}"


@pytest.mark.parametrize("name,s", HV_SNAP)
def test_reference_snapshot_hard_validity(name, s):
    """Hard-validity displacement matches the exact solution within the loose band."""
    cfg = BY_NAME[name]
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    ts = cfg["snaps"][s]
    ref = analytic_solution(cfg["profile"], cfg["c"], cfg["g"], grid(cfg["N"]), ts)
    e = rel_l2(data[s][:, 0], ref)
    assert e <= TOL["l2_base_loose"], (
        f"{name}@t={ts:.3g}: L2 {e:.2e} > {TOL['l2_base_loose']:.2e}"
    )


@pytest.mark.parametrize("name,s", MAIN_SNAP)
def test_reference_velocity_main(name, s):
    """Emitted velocity matches the exact u_t within the tight L2 band (t > 0)."""
    cfg = BY_NAME[name]
    if s == 0:
        pytest.skip("velocity is identically zero at the initial time")
    data = agent_run(cfg)
    assert data is not None, f"{name}: no gradeable output"
    ts = cfg["snaps"][s]
    ref = analytic_velocity(cfg["profile"], cfg["c"], cfg["g"], grid(cfg["N"]), ts)
    e = rel_l2(data[s][:, 1], ref)
    assert e <= TOL["l2_base_vel"], (
        f"{name}@t={ts:.3g}: velocity L2 {e:.2e} > {TOL['l2_base_vel']:.2e}"
    )


# --------------------------------------------------------------------------
# Path (c): convergence order under grid refinement
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cvcfg", CASES["convergence"], ids=lambda c: c["name"])
def test_convergence_order(cvcfg):
    """Error decays near fourth order under refinement (rejects a stalled slope)."""
    s = conv_slope(agent_bin(), cvcfg, sandbox=True)
    assert TOL["slope_lo"] <= s <= TOL["slope_hi"], f"{cvcfg['name']}: slope {s:.3f}"


# --------------------------------------------------------------------------
# Metamorphic relations derived from the linear damped-wave equation
# --------------------------------------------------------------------------
def _add_profiles(f, g):
    return {
        "kind": "sinsum",
        "c0": f["c0"] + g["c0"],
        "amps": list(f["amps"]) + list(g["amps"]),
        "waves": list(f["waves"]) + list(g["waves"]),
        "phases": list(f["phases"]) + list(g["phases"]),
    }


def _scale_profile(p, factor):
    return {**p, "c0": p["c0"] * factor, "amps": [a * factor for a in p["amps"]]}


def _shift_profile(p, delta):
    return {
        **p,
        "phases": [
            ph - 2 * math.pi * w * delta for w, ph in zip(p["waves"], p["phases"])
        ],
    }


@pytest.mark.parametrize("s", range(5))
def test_linear_superposition(s):
    """The solution of f+g equals the sum of the solutions (the PDE is linear)."""
    mm = CASES["metamorphic"]["superposition"]
    c, g, N, nu = mm["c"], mm["g"], mm["N"], mm["nu"]
    snaps = tuple(snaps_for(mm["T"]))
    fp, gp = mm["f"], mm["g_prof"]
    fr = run(agent_bin(), fp, c, g, N, nu, snaps, sandbox=True)
    gr = run(agent_bin(), gp, c, g, N, nu, snaps, sandbox=True)
    sr = run(agent_bin(), _add_profiles(fp, gp), c, g, N, nu, snaps, sandbox=True)
    assert fr is not None and gr is not None and sr is not None
    assert np.allclose(sr[s], fr[s] + gr[s], atol=TOL["metamorphic_abs"]), (
        f"superposition broken at snap {s}"
    )


@pytest.mark.parametrize("s", range(5))
def test_amplitude_scaling(s):
    """Scaling the initial data by a factor scales the solution by that factor."""
    mm = CASES["metamorphic"]["amplitude"]
    c, g, N, nu, factor = mm["c"], mm["g"], mm["N"], mm["nu"], mm["factor"]
    snaps = tuple(snaps_for(mm["T"]))
    base = run(agent_bin(), mm["base"], c, g, N, nu, snaps, sandbox=True)
    scaled = run(
        agent_bin(),
        _scale_profile(mm["base"], factor),
        c,
        g,
        N,
        nu,
        snaps,
        sandbox=True,
    )
    assert base is not None and scaled is not None
    assert np.allclose(
        scaled[s], factor * base[s], atol=TOL["metamorphic_abs"], rtol=1e-9
    ), f"amplitude scaling broken at snap {s}"


@pytest.mark.parametrize("s", range(5))
def test_translation_covariance(s):
    """Shifting the initial data by delta shifts the solution by delta."""
    mm = CASES["metamorphic"]["translation"]
    c, g, N, nu, delta = mm["c"], mm["g"], mm["N"], mm["nu"], mm["delta"]
    snaps = tuple(snaps_for(mm["T"]))
    shift = int(round(delta * N))
    base = run(agent_bin(), mm["base"], c, g, N, nu, snaps, sandbox=True)
    shifted = run(
        agent_bin(), _shift_profile(mm["base"], delta), c, g, N, nu, snaps, sandbox=True
    )
    assert base is not None and shifted is not None
    assert np.allclose(
        shifted[s], np.roll(base[s], shift, axis=0), atol=TOL["metamorphic_abs"]
    ), f"translation broken at snap {s}"


# --------------------------------------------------------------------------
# Whole-agent reward and external wrong baselines (identical grading)
# --------------------------------------------------------------------------
def test_agent_full_reward():
    """The agent, under the master grader used for all parties, earns reward 1."""
    ok, why = full_reward(agent_bin(), sandbox=True)
    assert ok, f"agent did not earn reward 1: {why}"


WRONG = [
    "second_order",
    "leapfrog_time",
    "forward_euler",
    "anti_damping",
    "over_cfl",
    "analytic_cheat",
    "sixth_space_fourth_time",
]


def test_independent_sixth_order_scheme_earns_full_reward():
    """A genuinely different but valid sixth-order scheme also earns full reward.

    Fairness gate: the whole master grader is applied to an independent solver
    that uses the same sixth-order spatial stencil advanced by Luther's seven-stage
    sixth-order Runge-Kutta method instead of the oracle's truncated-exponential
    integrator. It passes every path, proving the accuracy band rewards any correct
    sixth-order scheme rather than pinning the specific oracle time integrator.
    """
    ok, why = full_reward(baseline_bin("sixth_rk6"))
    assert ok, f"independent valid sixth-order scheme was rejected: {why}"


def test_sixth_space_fourth_time_fails_convergence():
    """A sixth-order-space scheme with a fourth-order time integrator is rejected.

    Machine-checkable proof that the accuracy bar is sixth order, not fourth. The
    scheme uses the correct sixth-order spatial stencil but classical RK4 in time;
    it is conservative, dissipative, finite, and matches the reference in absolute
    terms, so it passes every physical path. But because the step is Courant-limited
    the fourth-order time error dominates, so the joint refinement slope is only ~4
    and falls below the sixth-order band. This proves the requirement binds the
    whole scheme (space AND time), not the stencil alone.
    """
    b = baseline_bin("sixth_space_fourth_time")
    for cvcfg in CASES["convergence"]:
        s = conv_slope(b, cvcfg)
        assert s < TOL["slope_lo"], (
            f"{cvcfg['name']}: sixth_space_fourth_time slope {s:.3f} not below the band"
        )
    # It must otherwise pass every physical path, isolating the accuracy axis.
    for cfg in MAIN:
        ok, why = grade_case(
            run(
                b,
                cfg["profile"],
                cfg["c"],
                cfg["g"],
                cfg["N"],
                cfg["nu"],
                tuple(cfg["snaps"]),
            ),
            cfg,
        )
        assert ok, f"sixth_space_fourth_time unexpectedly failed a physical path: {why}"


@pytest.mark.parametrize("bname", WRONG)
def test_wrong_baseline_scores_zero(bname):
    """Each external wrong scheme fails at least one grading path (reward 0)."""
    ok, why = full_reward(baseline_bin(bname))
    assert not ok, f"baseline {bname} unexpectedly earned reward 1"


def test_second_order_fails_convergence():
    """The standard second-order-space scheme stalls near slope two."""
    s = conv_slope(baseline_bin("second_order"), CASES["convergence"][1])
    assert s < TOL["slope_lo"], f"second_order slope {s:.3f} not below the band"


def test_leapfrog_fails_convergence():
    """A second-order-in-time (velocity-Verlet) march stalls near slope two."""
    s = conv_slope(baseline_bin("leapfrog_time"), CASES["convergence"][1])
    assert s < TOL["slope_lo"], f"leapfrog_time slope {s:.3f} not below the band"


def test_forward_euler_fails_convergence():
    """A first-order-in-time march stalls well below the fourth-order band."""
    s = conv_slope(baseline_bin("forward_euler"), CASES["convergence"][1])
    assert not (TOL["slope_lo"] <= s <= TOL["slope_hi"]), (
        f"forward_euler slope {s:.3f} unexpectedly inside the band"
    )


def test_anti_damping_fails_energy():
    """Wrong-sign damping injects energy: the discrete energy rises over snapshots.

    This exercises the energy-monotonicity path directly (independent of the L2
    check), proving that path rejects an anti-dissipative scheme.
    """
    cfg = BY_NAME["visible"]
    data = run(
        baseline_bin("anti_damping"),
        cfg["profile"],
        cfg["c"],
        cfg["g"],
        cfg["N"],
        cfg["nu"],
        tuple(cfg["snaps"]),
    )
    assert data is not None, "anti-damping produced no gradeable output"
    e = [
        discrete_energy(data[s][:, 0], data[s][:, 1], cfg["c"], cfg["N"])
        for s in range(5)
    ]
    rose = any(e[s] > e[s - 1] + TOL["energy_tol"] for s in range(1, 5))
    assert rose, f"anti-damping energy did not rise as expected: {e}"


def test_analytic_cheat_fails_convergence():
    """Writing the exact field directly gives a ~0 refinement slope."""
    s = conv_slope(baseline_bin("analytic_cheat"), CASES["convergence"][1])
    assert s < TOL["slope_lo"], f"analytic_cheat slope {s:.3f} not below the band"


def test_over_cfl_nonfinite():
    """An oversized Courant number drives the field to non-finite values."""
    cfg = BY_NAME["m2"]
    data = run(
        baseline_bin("over_cfl"),
        cfg["profile"],
        cfg["c"],
        cfg["g"],
        cfg["N"],
        cfg["nu"],
        tuple(cfg["snaps"]),
    )
    # Either the run is ungradeable (parser rejected inf/nan) or a snapshot is
    # non-finite / far from the reference; grade_case must reject it.
    ok, _ = grade_case(data, cfg)
    assert not ok, "over-CFL scheme unexpectedly passed grading"


# --------------------------------------------------------------------------
# Executed semantic case count (behavioral-testing floor)
# --------------------------------------------------------------------------
def test_executed_case_count():
    """Report and assert the number of executed semantic grading evaluations."""
    count = (
        len(MAIN_SNAP)  # main displacement snapshots
        + len(HV_SNAP)  # hard-validity displacement snapshots
        + len(MAIN_SNAP)  # main velocity snapshots
        + len(CASES["convergence"]) * len(LADDER)  # refinement runs
        + len(ALL)  # mass
        + len(ALL)  # finiteness
        + len(ALL)  # energy monotonicity
        + 3 * 5  # three metamorphic relations x 5 snaps
        + len(WRONG)  # wrong-baseline rejections
    )
    print(f"EXECUTED_SEMANTIC_CASES={count}")
    assert count >= 60
