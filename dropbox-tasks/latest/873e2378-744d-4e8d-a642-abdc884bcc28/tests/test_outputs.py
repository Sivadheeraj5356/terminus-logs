"""Verifier for the full-plane Faddeeva line-shape engine task.

The agent's /app/faddeeva.js is run on a held-out batch of complex arguments
and every printed line (ln|w| and arg w) is graded against a high-precision
reference. The reference lives only here in the verifier (never in the task
image) and the held-out inputs differ from the shipped sample, so the program
has to evaluate w(z) rather than echo memorized numbers.

ln|w| is graded to 5e-9 ABSOLUTE while its magnitude reaches 9e14, so the
comparison is done in decimal arithmetic: parsing the printed value into a
float would round away everything below ~0.1 at that size and grade the parse,
not the program. The phase is order one and is compared as a float, circularly,
so the branch point at pi is not a trap.

Each reference row is tagged with a band so failures point at the regime that
broke: the origin, the upper half-plane bulk, the exploding side below the axis
(growth), the reflection-dominated side (shadow), the near-diagonal strip where
the two reflection terms interact (ridge), and the two axes.

The reference was fixed at authoring time two independent ways that agree to
about 1e-18 relative: mpmath's exp(-z^2)*erfc(-i z) at high precision, and the
contour-integral form evaluated by quadrature (through the reflection
w(z) = 2 exp(-z^2) - w(-z) below the axis), with the functional equation
w(z) + w(-z) = 2 exp(-z^2) asserted on every row. That is far tighter than the
5e-9 the agent is graded to.
"""
import functools
import json
import math
import os
import subprocess
import time
from decimal import Decimal, getcontext

getcontext().prec = 60

REFERENCE_PATH = os.environ.get("REFERENCE_PATH", "/tests/reference.jsonl")
ENGINE_PATH = os.environ.get("ENGINE_PATH", "/app/faddeeva.js")

# Grading bars, both absolute: |L - L_ref| <= TOL_LN on the log-modulus,
# circular distance <= TOL_ARG on the phase.
TOL_LN = Decimal("5e-9")
TOL_ARG = 5e-9
TWO_PI = 2 * math.pi

# Large-batch timing gate. A correct O(1)-per-call evaluation finishes far
# under this; the margin only rules out a per-call cost that scales with a
# fine grid or a term count that grows with the argument.
TIMING_BATCH = 60000
TIME_BUDGET_SEC = 30.0


def _load_reference():
    rows = []
    with open(REFERENCE_PATH) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@functools.lru_cache(maxsize=1)
def _run():
    """Run the engine once on the held-out inputs; cached so the subprocess is
    launched a single time."""
    rows = _load_reference()
    inputs_path = os.environ.get("INPUTS_PATH", "/tmp/heldout_inputs.jsonl")
    with open(inputs_path, "w", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps({"x": r["x"], "y": r["y"]}) + "\n")
    proc = subprocess.run(
        ["node", ENGINE_PATH, inputs_path],
        capture_output=True, text=True, timeout=120,
    )
    return rows, proc


def _parse_ln(tok):
    """Parse the printed log-modulus at full decimal precision. Reject
    anything that is not a plain finite number."""
    try:
        val = Decimal(tok)
    except Exception:
        raise AssertionError(f"log-modulus is not a number: {tok!r}")
    assert val.is_finite(), f"log-modulus is not finite: {tok!r}"
    return val


def _parse_arg(tok):
    try:
        val = float(tok)
    except ValueError:
        raise AssertionError(f"phase is not a number: {tok!r}")
    assert math.isfinite(val), f"phase is not finite: {tok!r}"
    return val


def _results():
    rows, proc = _run()
    assert proc.returncode == 0, (
        f"node exited {proc.returncode}; stderr:\n{proc.stderr[:1000]}"
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip() != ""]
    assert len(lines) == len(rows), (
        f"expected {len(rows)} output lines, got {len(lines)}"
    )
    out = []
    for r, ln in zip(rows, lines):
        parts = ln.split()
        assert len(parts) == 2, f"expected two numbers per line, got: {ln!r}"
        out.append((r, _parse_ln(parts[0]), _parse_arg(parts[1])))
    return out


def _errors(row, ln_val, arg_val):
    dln = abs(ln_val - Decimal(row["ln"]))
    d = abs(arg_val - row["arg"]) % TWO_PI
    darg = min(d, TWO_PI - d)
    return dln, darg


def _out_of_tol(row, ln_val, arg_val):
    dln, darg = _errors(row, ln_val, arg_val)
    return dln > TOL_LN or darg > TOL_ARG


def _band(band):
    return [t for t in _results() if t[0]["band"] == band]


def _describe(r):
    return f"z=({r['x']},{r['y']}) band={r['band']}"


def _check(rows):
    bad = []
    for (r, ln_val, arg_val) in rows:
        if _out_of_tol(r, ln_val, arg_val):
            dln, darg = _errors(r, ln_val, arg_val)
            bad.append((r, float(dln), darg))
    assert not bad, "values outside tolerance: " + "; ".join(
        f"{_describe(r)} dln={dl:.2e} darg={da:.2e}" for (r, dl, da) in bad[:12]
    )


def test_engine_file_exists():
    """The deliverable /app/faddeeva.js must be present."""
    assert os.path.isfile(ENGINE_PATH), f"{ENGINE_PATH} was not created"


def test_output_shape():
    """One finite log-modulus/phase pair per request."""
    results = _results()
    assert len(results) > 0


def test_origin():
    """Small |z| about the origin, both half-planes."""
    rows = _band("origin")
    assert len(rows) > 0
    _check(rows)


def test_upper_half_plane():
    """The bounded upper half-plane, where w is order one."""
    rows = _band("upper")
    assert len(rows) > 0
    _check(rows)


def test_growth():
    """Below the axis with y^2 - x^2 large: the exploding side, where the
    log-modulus reaches 9e14 and is still graded to 5e-9 absolute."""
    rows = _band("growth")
    assert len(rows) > 0
    _check(rows)


def test_shadow():
    """Below the axis with x^2 - y^2 large: the reflection-dominated side."""
    rows = _band("shadow")
    assert len(rows) > 0
    _check(rows)


def test_ridge():
    """Below the axis near |y| = |x|, where the two reflection terms are
    comparable and the square difference cancels to order one."""
    rows = _band("ridge")
    assert len(rows) > 0
    _check(rows)


def test_real_axis():
    """Pure real argument (y = 0)."""
    rows = _band("real_axis")
    assert len(rows) > 0
    _check(rows)


def test_imag_axis():
    """Pure imaginary argument (x = 0), both signs of y."""
    rows = _band("imag_axis")
    assert len(rows) > 0
    _check(rows)


def test_all_within_tolerance():
    """Every held-out pair must pass both bars."""
    results = _results()
    bad = [r for (r, ln_val, arg_val) in results
           if _out_of_tol(r, ln_val, arg_val)]
    assert not bad, (
        f"{len(bad)} of {len(results)} values outside tolerance"
    )


def _timing_batch(path):
    """Write a large deterministic batch spanning the full plane, for the
    speed and finiteness gate. No reference is needed: it only checks the
    program keeps up and never prints a non-finite value."""
    state = 2463534242

    def rnd():
        nonlocal state
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        return state / 0xFFFFFFFF

    with open(path, "w", newline="\n") as fh:
        for _ in range(TIMING_BATCH):
            x = -3.0e7 + rnd() * 6.0e7
            u = rnd()
            if u < 0.3:
                y = (rnd() - 0.5) * 4e-3   # hugging the real axis
            else:
                y = -3.0e7 + rnd() * 6.0e7
            fh.write(json.dumps({"x": x, "y": y}) + "\n")


def test_large_batch_speed_and_finite():
    """A big batch must be evaluated within the wall-clock budget and every
    value must be finite."""
    path = os.environ.get("TIMING_PATH", "/tmp/timing_inputs.jsonl")
    _timing_batch(path)
    start = time.monotonic()
    proc = subprocess.run(
        ["node", ENGINE_PATH, path],
        capture_output=True, text=True, timeout=int(TIME_BUDGET_SEC) + 90,
    )
    elapsed = time.monotonic() - start
    assert proc.returncode == 0, (
        f"node exited {proc.returncode}; stderr:\n{proc.stderr[:1000]}"
    )
    vals = proc.stdout.split()
    assert len(vals) == TIMING_BATCH * 2, (
        f"expected {TIMING_BATCH * 2} numbers, got {len(vals)}"
    )
    nonfinite = 0
    for v in vals:
        try:
            d = Decimal(v)
            if not d.is_finite():
                nonfinite += 1
        except Exception:
            nonfinite += 1
    assert nonfinite == 0, f"{nonfinite} non-finite values in the large batch"
    assert elapsed <= TIME_BUDGET_SEC, (
        f"large batch took {elapsed:.1f}s, over the {TIME_BUDGET_SEC:.0f}s budget"
    )
