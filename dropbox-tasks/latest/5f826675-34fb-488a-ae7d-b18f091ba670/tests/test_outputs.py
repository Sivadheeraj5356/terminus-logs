"""Verifier for the bound-state-energies task.

The solver must be a Dart program at /app/solve.dart that takes an input-batch
path and an output path. This verifier runs that program itself -- on a trusted
copy of the shipped batch and on a held-out batch of wells the agent never saw --
and checks that it reports, for every well, the requested number of lowest
eigenvalues of  -1/2 psi'' + V psi = E psi, ascending and each within 1e-5
(absolute) of a reference the verifier computes at run time.

Design notes that close known shortcuts:
  * Reference spectra are computed here (ref_solver.reference_spectrum), not
    stored as files, so a solver that reads the verifier directory finds only
    Python source it cannot execute -- porting it would mean solving the problem.
  * The verifier runs the solver on the TRUSTED /tests copies of the inputs and
    scores against references built from the same trusted copies, so editing the
    agent-writable /app inputs cannot move the target.
  * A held-out batch the agent never saw defeats hardcoded or transcribed answers.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Make the verifier-owned reference solver importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ref_solver import reference_spectrum  # noqa: E402

APP = Path(os.environ.get("APP_DIR", "/app"))
TEST_DIR = Path(os.environ.get("TEST_DIR", "/tests"))
DART = os.environ.get("DART_BIN", "dart")

SOLVER = APP / "solve.dart"
MAIN_INPUT = TEST_DIR / "potentials.json"   # trusted copy, not agent-writable /app
HOLD_INPUT = TEST_DIR / "holdout.json"
TOL = 1e-5


def _load_instances(path):
    return json.loads(Path(path).read_text())["instances"]


def _reference(path):
    return {inst["id"]: reference_spectrum(inst) for inst in _load_instances(path)}


MAIN_REF = _reference(MAIN_INPUT)
HOLD_REF = _reference(HOLD_INPUT)

_cache = {}


def _run(inp: Path):
    """Run the agent's Dart solver on `inp`; return {ok, reason, rows}."""
    key = str(inp)
    if key in _cache:
        return _cache[key]
    res = {"ok": False, "reason": "", "rows": None}
    out = Path(tempfile.gettempdir()) / f"bss_out_{abs(hash(key))}.json"
    if not SOLVER.exists():
        res["reason"] = "no Dart solver found at /app/solve.dart"
        _cache[key] = res
        return res
    try:
        if out.exists():
            out.unlink()
    except OSError:
        pass
    try:
        proc = subprocess.run(
            [DART, str(SOLVER), str(inp), str(out)],
            capture_output=True, text=True, timeout=240,
        )
    except FileNotFoundError:
        res["reason"] = "the 'dart' runtime is not available"
        _cache[key] = res
        return res
    except subprocess.TimeoutExpired:
        res["reason"] = "solver timed out"
        _cache[key] = res
        return res
    if proc.returncode != 0:
        res["reason"] = f"solver exited {proc.returncode}: {proc.stderr[-400:]}"
        _cache[key] = res
        return res
    if not out.exists():
        res["reason"] = "solver did not write the output file"
        _cache[key] = res
        return res
    try:
        res["data"] = json.loads(out.read_text())
        res["rows"] = res["data"].get("results") if isinstance(res["data"], dict) else None
        res["ok"] = True
    except ValueError as exc:
        res["reason"] = f"output is not valid JSON: {exc}"
    _cache[key] = res
    return res


def _strict_map(rows):
    """Validate {'results': [...]} strictly and return {id: energies}.

    Each row must be a dict with exactly the keys {'id', 'energies'}; ids must be
    unique (no duplicate rows silently overwriting each other). Returns None on
    any violation."""
    if not isinstance(rows, list):
        return None
    out = {}
    for row in rows:
        if not isinstance(row, dict) or set(row.keys()) != {"id", "energies"}:
            return None
        if not isinstance(row["energies"], list):
            return None
        out[row["id"]] = row["energies"]
    if len(out) != len(rows):        # duplicate ids collapsed the map
        return None
    return out


def test_dart_solver_present():
    """A Dart program must be delivered at /app/solve.dart."""
    assert SOLVER.exists(), "expected the solver at /app/solve.dart; none was found"


def test_solver_runs_and_writes_output():
    """Running `dart /app/solve.dart <in> <out>` succeeds and writes output."""
    r = _run(MAIN_INPUT)
    assert r["ok"], f"could not run the Dart solver on the batch: {r['reason']}"


def test_output_matches_schema_exactly():
    """Output is {'results': [{'id','energies'}]} with no extra row keys or
    duplicate ids."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None, (
        "output must be a results list of rows with exactly the keys 'id' and "
        "'energies', and no duplicate ids"
    )


def test_every_well_reported_once():
    """Every input well id appears exactly once in the results."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None, "output does not match the documented schema"
    assert set(got.keys()) == set(MAIN_REF.keys()), (
        "results must cover exactly the input wells, with no missing or extra ids"
    )


def test_correct_number_of_levels():
    """Each well reports exactly k energies (k = number of reference levels)."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None
    for iid, ref in MAIN_REF.items():
        assert len(got[iid]) == len(ref), (
            f"{iid}: expected {len(ref)} energies, got {len(got[iid])}"
        )


def test_energies_are_finite_numbers():
    """Reported energies are real, finite numbers."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None
    for iid, energies in got.items():
        for e in energies:
            assert isinstance(e, (int, float)) and not isinstance(e, bool) and math.isfinite(e), (
                f"{iid}: energy {e!r} is not a finite number"
            )


def test_energies_sorted_ascending():
    """Each well's energies are in ascending order, as requested."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None
    for iid in MAIN_REF:
        assert got[iid] == sorted(got[iid]), f"{iid}: energies are not ascending"


@pytest.mark.parametrize("iid", sorted(MAIN_REF.keys()))
def test_spectrum_matches_reference(iid):
    """The k lowest energies of each shipped well match the reference within 1e-5."""
    r = _run(MAIN_INPUT)
    assert r["ok"], r["reason"]
    got = _strict_map(r["rows"])
    assert got is not None, "output does not match the documented schema"
    worst = max(abs(float(g) - t) for g, t in zip(got[iid], MAIN_REF[iid]))
    assert worst <= TOL, (
        f"{iid}: largest absolute energy error {worst:.2e} exceeds tolerance {TOL:.0e}"
    )


def test_solver_generalizes_to_unseen_wells():
    """Run the same Dart program on a held-out batch it never saw; every spectrum
    must match within 1e-5. Solutions that hardcode the shipped answers, or that
    were not actually computed by the Dart program, fail here."""
    r = _run(HOLD_INPUT)
    assert r["ok"], f"solver failed on the held-out batch: {r['reason']}"
    got = _strict_map(r["rows"])
    assert got is not None, "held-out output does not match the documented schema"
    assert set(got.keys()) == set(HOLD_REF.keys()), (
        "held-out results must cover exactly the held-out wells"
    )
    for iid, ref in HOLD_REF.items():
        assert len(got[iid]) == len(ref), f"{iid}: wrong number of levels"
        worst = max(abs(float(g) - t) for g, t in zip(got[iid], ref))
        assert worst <= TOL, (
            f"{iid}: held-out energy error {worst:.2e} exceeds tolerance {TOL:.0e}"
        )
