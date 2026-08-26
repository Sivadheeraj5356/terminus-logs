"""Behavioral verifier for the isotonic regression fitter.

The program under test reads one JSON job ``{"inputs": [<input>, ...]}`` on
standard input and writes ``{"results": [{"pred": [...]}, ...]}`` on standard
output, one result per input in order. Correctness is that of
``sklearn.isotonic.IsotonicRegression`` as described in the task: a
sample-weighted isotonic fit (non-decreasing when ``increasing`` is true,
non-increasing otherwise) with linear interpolation between fitted points and
``out_of_bounds="clip"`` clamping of out-of-range queries. Each expected value
in ``corpus.json`` was produced by an independent reference implementation of
the same estimator.

The whole corpus is fed to the program once and each input is checked
independently to a floating-point tolerance, so a partial implementation still
scores on the cases it handles correctly.
"""
import json
import math
import os
import shutil
import subprocess

import pytest

APP = "/app"
BIN = "/usr/local/bin/isoreg"
BUILT = "/app/dist/isoreg.built"
CORPUS = os.path.join(os.path.dirname(__file__), "corpus.json")
RUN_TIMEOUT_SEC = 120
ATOL = 1e-6
RTOL = 1e-6


def _load():
    with open(CORPUS, encoding="utf-8") as f:
        return json.load(f)


CASES = _load()


def _build():
    if not os.path.exists(BUILT):
        make = shutil.which("make") or "make"
        r = subprocess.run([make, "dist/isoreg.built"], cwd=APP,
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, f"build failed: {r.stderr}"
    assert os.path.exists(BUILT), f"build marker not found at {BUILT}"
    return BIN


def _run_all(binary):
    job = {"inputs": [c["input"] for c in CASES]}
    r = subprocess.run([binary], input=json.dumps(job),
                       capture_output=True, text=True, timeout=RUN_TIMEOUT_SEC)
    assert r.returncode == 0, f"program exited nonzero: {r.stderr}"
    doc = json.loads(r.stdout.strip())
    return doc["results"]


@pytest.fixture(scope="session")
def results():
    binary = _build()
    return _run_all(binary)


def _close(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if not math.isclose(x, y, rel_tol=RTOL, abs_tol=ATOL):
            return False
    return True


def test_result_count(results):
    """One result object is produced for every input case."""
    assert len(results) == len(CASES), (
        f"expected {len(CASES)} results, got {len(results)}")


def test_result_shape(results):
    """Every result carries a numeric pred list, one value per query."""
    bad = []
    for i, (c, r) in enumerate(zip(CASES, results)):
        pred = r.get("pred") if isinstance(r, dict) else None
        if not isinstance(pred, list) or len(pred) != len(c["input"]["queries"]):
            bad.append(i)
    assert not bad, f"malformed pred at indices: {bad[:5]}"


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_case(results, idx):
    """Each case matches the reference isotonic predictions within tolerance."""
    c = CASES[idx]
    want = c["expected"]["pred"]
    got = results[idx].get("pred") if idx < len(results) else None
    assert got is not None and _close(got, want), (
        f"case[{idx}] n={len(c['input']['x'])} "
        f"increasing={c['input']['increasing']} "
        f"weighted={c['input']['weight'] is not None}: "
        f"reference[:4]={want[:4]}, got[:4]={(got or [])[:4]}")
