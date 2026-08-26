"""Scientific-computing verifier for finite-volume-burgers: multi-kit finite-volume-burgers staging with shared
truck volume, bay holding, flat hire, peak surcharge, and shock-capture bay fee."""

from __future__ import annotations

import glob
import os
import re
import subprocess
import tempfile

import pytest

APP = "/app"
MODEL = os.path.join(APP, "model.mzn")
INST = os.path.join(APP, "instance.dzn")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
HIDDEN = os.path.join(FIX, "instance_hidden.dzn")
PERRUN = os.path.join(FIX, "perrun.mzn")
FLATHOLD = os.path.join(FIX, "flathold.mzn")
SPLITRUN = os.path.join(FIX, "splitrun.mzn")
NOPEAK = os.path.join(FIX, "nopeak.mzn")
NOSHOCK = os.path.join(FIX, "noshock.mzn")
BATTERY = sorted(glob.glob(os.path.join(FIX, "battery", "*.dzn")))
HIREONLY_INST = sorted(glob.glob(os.path.join(FIX, "hireonly", "*.dzn")))

ALL_INSTANCES = [INST, HIDDEN] + BATTERY
GAP_PERRUN = os.path.join(FIX, "gap_perrun.dzn")
GAP_FLATHOLD = os.path.join(FIX, "gap_flathold.dzn")
GAP_SPLIT = os.path.join(FIX, "gap_split.dzn")
GAP_NOPEAK = os.path.join(FIX, "gap_nopeak.dzn")
GAP_NOSHOCK = os.path.join(FIX, "gap_noshock.dzn")
PERRUN_INSTANCES = [GAP_PERRUN]
FLATHOLD_INSTANCES = [GAP_FLATHOLD]
SPLITRUN_INSTANCES = [GAP_SPLIT]
NOPEAK_INSTANCES = [GAP_NOPEAK]
NOSHOCK_INSTANCES = [GAP_NOSHOCK]


def _parse_instance(path):
    """Parse scalars, vectors, and 2-D demand/price matrices from a .dzn file."""
    text = open(path).read()

    def scalar(name):
        return int(re.search(rf"\b{name}\s*=\s*(\d+)\s*;", text).group(1))

    def vec(name):
        body = re.search(rf"\b{name}\s*=\s*\[([^\]]*)\]\s*;", text).group(1)
        return [int(v) for v in re.findall(r"-?\d+", body)]

    def mat(name):
        m = re.search(rf"\b{name}\s*=\s*\[(.*?)\];", text, re.S)
        assert m, name
        rows = []
        for part in m.group(1).split("|"):
            nums = [int(v) for v in re.findall(r"-?\d+", part)]
            if nums:
                rows.append(nums)
        return rows

    P, T = scalar("P"), scalar("T")
    d, c = mat("d"), mat("c")
    assert len(d) == P and all(len(r) == T for r in d)
    assert len(c) == P and all(len(r) == T for r in c)
    return {
        "T": T,
        "P": P,
        "B": scalar("B"),
        "v": vec("v"),
        "d": d,
        "c": c,
        "shockwave": vec("shockwave"),
        "F": scalar("F"),
        "A": scalar("A"),
        "h": scalar("h"),
        "smin": vec("smin"),
        "G": scalar("G"),
        "PeakV": scalar("PeakV"),
        "S": scalar("S"),
        "W": scalar("W"),
    }


def _solve(model, inst, timeout=120):
    """Run MiniZinc/Chuffed and return [q1, q2] from the optimal block."""
    d = _parse_instance(inst)
    r = subprocess.run(
        ["minizinc", "--solver", "chuffed", "-t", "110000", model, inst],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    blocks = [b for b in r.stdout.split("----------") if "q1=" in b and "q2=" in b]
    assert blocks, "model emitted no q1/q2 solution: " + r.stdout
    block = blocks[-1]
    m1 = re.search(r"q1=\s*\[([^\]]*)\]", block)
    m2 = re.search(r"q2=\s*\[([^\]]*)\]", block)
    assert m1 and m2, block
    q1 = [int(v) for v in re.findall(r"-?\d+", m1.group(1))]
    q2 = [int(v) for v in re.findall(r"-?\d+", m2.group(1))]
    assert len(q1) == d["T"] and len(q2) == d["T"], block
    return [q1, q2]


def _inventory(q, inst):
    """Return inv[p][t] lists, or None if any kit breaches demand/reserve."""
    d = _parse_instance(inst)
    inv = [[0] * d["T"] for _ in range(d["P"])]
    for p in range(d["P"]):
        cur = 0
        for t in range(d["T"]):
            if q[p][t] < 0:
                return None
            cur = cur + q[p][t] - d["d"][p][t]
            if cur < d["smin"][p]:
                return None
            inv[p][t] = cur
    return inv


def _feasible(q, inst):
    """Purchases meet every kit demand and reserve."""
    d = _parse_instance(inst)
    if len(q) != d["P"] or any(len(row) != d["T"] for row in q):
        return False
    return _inventory(q, inst) is not None


def _runs(vol, B):
    return 0 if vol == 0 else (vol + B - 1) // B


def _fleet_cost(runs, F, A, kmax):
    """Cheapest owned fleet plus flat weekly hire for overflow weeks."""
    return min(A * k + F * sum(1 for r in runs if r > k) for k in range(kmax + 1))


def _objective(q, inst):
    """Recompute purchase + best fleet + bay holding + peak + shockwave fees."""
    d = _parse_instance(inst)
    inv = _inventory(q, inst)
    assert inv is not None
    buy = sum(d["c"][p][t] * q[p][t] for p in range(d["P"]) for t in range(d["T"]))
    vols = [sum(d["v"][p] * q[p][t] for p in range(d["P"])) for t in range(d["T"])]
    runs = [_runs(vol, d["B"]) for vol in vols]
    caps = [sum(d["d"][p]) + d["smin"][p] for p in range(d["P"])]
    vcap = sum(d["v"][p] * caps[p] for p in range(d["P"]))
    kmax = vcap // d["B"] + 1
    fleet = _fleet_cost(runs, d["F"], d["A"], kmax)
    hold = 0
    for t in range(d["T"]):
        stock_v = sum(d["v"][p] * inv[p][t] for p in range(d["P"]))
        hold += d["h"] * max(0, stock_v - d["G"])
    peak = d["S"] * sum(1 for vol in vols if vol > d["PeakV"])
    shockwave = d["W"] * sum(
        1 for t, vol in enumerate(vols) if d["shockwave"][t] == 1 and vol > 0
    )
    return buy + fleet + hold + peak + shockwave


def _dp_optimum(inst):
    """Independent optimum: enumerate K; DP over (inv1, inv2)."""
    d = _parse_instance(inst)
    T, P = d["T"], d["P"]
    assert P == 2
    v, dem, c = d["v"], d["d"], d["c"]
    shockwave = d["shockwave"]
    B, F, A, h = d["B"], d["F"], d["A"], d["h"]
    smin, G, PeakV, S, W = d["smin"], d["G"], d["PeakV"], d["S"], d["W"]
    cap = [sum(dem[p]) + smin[p] for p in range(P)]
    vcap = sum(v[p] * cap[p] for p in range(P))
    kmax = vcap // B + 1

    def hold(i0, i1):
        return h * max(0, v[0] * i0 + v[1] * i1 - G)

    best = None
    for k in range(kmax + 1):
        prev = {}
        for i0 in range(smin[0], cap[0] + 1):
            for i1 in range(smin[1], cap[1] + 1):
                q0, q1 = i0 + dem[0][0], i1 + dem[1][0]
                if q0 < 0 or q1 < 0 or q0 > cap[0] or q1 > cap[1]:
                    continue
                vol = v[0] * q0 + v[1] * q1
                runs = _runs(vol, B)
                prev[(i0, i1)] = (
                    c[0][0] * q0
                    + c[1][0] * q1
                    + (F if runs > k else 0)
                    + hold(i0, i1)
                    + (S if vol > PeakV else 0)
                    + (W if shockwave[0] == 1 and vol > 0 else 0)
                )
        for t in range(1, T):
            cur = {}
            for (p0, p1), base in prev.items():
                for i0 in range(smin[0], cap[0] + 1):
                    q0 = i0 - p0 + dem[0][t]
                    if q0 < 0 or q0 > cap[0]:
                        continue
                    for i1 in range(smin[1], cap[1] + 1):
                        q1 = i1 - p1 + dem[1][t]
                        if q1 < 0 or q1 > cap[1]:
                            continue
                        vol = v[0] * q0 + v[1] * q1
                        runs = _runs(vol, B)
                        cost = (
                            base
                            + c[0][t] * q0
                            + c[1][t] * q1
                            + (F if runs > k else 0)
                            + hold(i0, i1)
                            + (S if vol > PeakV else 0)
                            + (W if shockwave[t] == 1 and vol > 0 else 0)
                        )
                        key = (i0, i1)
                        if key not in cur or cost < cur[key]:
                            cur[key] = cost
            prev = cur
            if not prev:
                break
        if not prev:
            continue
        total = A * k + min(prev.values())
        if best is None or total < best:
            best = total
    assert best is not None
    return best


def _write_variant(base, dmat, cmat, shockwave=None):
    """Write a derived instance with new demand/price (and optional shockwave) arrays."""
    b = _parse_instance(base)
    fd, path = tempfile.mkstemp(suffix=".dzn")
    os.close(fd)

    def mat(rows):
        parts = ["| " + ", ".join(map(str, row)) for row in rows]
        return "[" + " ".join(parts) + " |]"

    st = shockwave if shockwave is not None else b["shockwave"]
    lines = [
        f"T = {b['T']};",
        f"P = {b['P']};",
        f"B = {b['B']};",
        f"v = [{', '.join(map(str, b['v']))}];",
        f"d = {mat(dmat)};",
        f"c = {mat(cmat)};",
        f"shockwave = [{', '.join(map(str, st))}];",
        f"F = {b['F']};",
        f"A = {b['A']};",
        f"h = {b['h']};",
        f"smin = [{', '.join(map(str, b['smin']))}];",
        f"G = {b['G']};",
        f"PeakV = {b['PeakV']};",
        f"S = {b['S']};",
        f"W = {b['W']};",
        "",
    ]
    open(path, "w").write("\n".join(lines))
    return path


_VARIANTS = ["reversed", "rotated", "scaled", "price_reversed", "swap_sku"]


def _variant(name):
    """Deterministic demand/price transforms of the public instance."""
    b = _parse_instance(INST)
    d, c = [row[:] for row in b["d"]], [row[:] for row in b["c"]]
    if name == "reversed":
        return [row[::-1] for row in d], [row[::-1] for row in c]
    if name == "rotated":
        r = 1
        return [row[r:] + row[:r] for row in d], [row[r:] + row[:r] for row in c]
    if name == "scaled":
        return [[2 * x for x in row] for row in d], c
    if name == "price_reversed":
        return d, [row[::-1] for row in c]
    if name == "swap_sku":
        return d[::-1], c[::-1]
    raise ValueError(name)


@pytest.mark.parametrize(
    "inst", ALL_INSTANCES, ids=[os.path.basename(p) for p in ALL_INSTANCES]
)
def test_model_attains_optimum(inst):
    """Agent model meets reserves and attains the recomputed minimum cost."""
    q = _solve(MODEL, inst)
    assert _feasible(q, inst), f"infeasible on {os.path.basename(inst)}: {q}"
    assert _objective(q, inst) == _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize("name", _VARIANTS)
def test_model_generalises_to_variants(name):
    """Optimum on permuted/scaled variants so answers are not hardcoded."""
    dmat, cmat = _variant(name)
    path = _write_variant(INST, dmat, cmat)
    try:
        q = _solve(MODEL, path)
        assert _feasible(q, path), f"{name}: {q}"
        assert _objective(q, path) == _dp_optimum(path), name
    finally:
        os.remove(path)


@pytest.mark.parametrize(
    "inst", PERRUN_INSTANCES, ids=[os.path.basename(p) for p in PERRUN_INSTANCES]
)
def test_per_run_model_suboptimal(inst):
    """Charging hire per overflow run is feasible but strictly costlier."""
    q = _solve(PERRUN, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) > _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize(
    "inst", FLATHOLD_INSTANCES, ids=[os.path.basename(p) for p in FLATHOLD_INSTANCES]
)
def test_flat_holding_model_suboptimal(inst):
    """Charging holding on all stock volume is feasible but costlier."""
    q = _solve(FLATHOLD, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) > _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize(
    "inst", SPLITRUN_INSTANCES, ids=[os.path.basename(p) for p in SPLITRUN_INSTANCES]
)
def test_split_run_model_suboptimal(inst):
    """Summing per-kit ceil runs over-counts shared trucks."""
    q = _solve(SPLITRUN, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) > _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize(
    "inst", NOPEAK_INSTANCES, ids=[os.path.basename(p) for p in NOPEAK_INSTANCES]
)
def test_no_peak_model_suboptimal(inst):
    """Omitting the peak surcharge yields a plan that is not optimal under true costs."""
    q = _solve(NOPEAK, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) > _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize(
    "inst", NOSHOCK_INSTANCES, ids=[os.path.basename(p) for p in NOSHOCK_INSTANCES]
)
def test_no_shockwave_model_suboptimal(inst):
    """Omitting the shock-capture bay fee yields a plan that is not optimal under true costs."""
    q = _solve(NOSHOCK, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) > _dp_optimum(inst), os.path.basename(inst)


@pytest.mark.parametrize(
    "inst", HIREONLY_INST, ids=[os.path.basename(p) for p in HIREONLY_INST]
)
def test_steady_demand_attains_optimum(inst):
    """On steady demand with peak/shockwave disabled, the agent model still hits the DP optimum."""
    q = _solve(MODEL, inst)
    assert _feasible(q, inst)
    assert _objective(q, inst) == _dp_optimum(inst)


def test_model_declares_decisions():
    """model.mzn declares decision variables and constraints, not a literal answer."""
    src = open(MODEL).read()
    assert "var" in src and "constraint" in src


def test_model_minimises():
    """The model optimises rather than fixing a target cost."""
    assert "minimize" in open(MODEL).read()


def test_model_uses_volume_peak_shockwave_and_bay():
    """A correct model must reference volume, peak, shockwave fee, and bay capacity."""
    src = open(MODEL).read()
    assert re.search(r"\bPeakV\b", src) and re.search(r"\bG\b", src)
    assert re.search(r"\bv\b", src) and re.search(r"\bW\b", src)
    assert re.search(r"\bshockwave\b", src)


def _strip_mzn_comments(src: str) -> str:
    """Drop MiniZinc comments so incidental path text in notes is ignored."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(line.split("%", 1)[0] for line in src.splitlines())


def _model_paths_outside_app(src: str) -> list[str]:
    """Return include/path literals that imply loading data outside /app."""
    code = _strip_mzn_comments(src)
    outside: list[str] = []
    for m in re.finditer(r'include\s+"([^"]+)"', code):
        path = m.group(1)
        if path.startswith("..") or (path.startswith("/") and not path.startswith("/app/")):
            outside.append(f'include "{path}"')
    for m in re.finditer(r'"(/[^"]+)"', code):
        path = m.group(1)
        if not path.startswith("/app/"):
            outside.append(path)
    for pat, label in (
        (r"\binstance_hidden\.dzn\b", "instance_hidden.dzn"),
        (r"\bfixtures/", "fixtures/"),
        (
            r"\bgap_(?:perrun|flathold|split|nopeak|noshock)\.dzn\b",
            "hidden gap fixture",
        ),
    ):
        if re.search(pat, code):
            outside.append(label)
    return outside


def test_model_reads_no_fixtures():
    """The model must not include or load files outside the agent workspace."""
    hits = _model_paths_outside_app(open(MODEL).read())
    assert not hits, f"model depends on paths outside /app: {sorted(set(hits))}"
