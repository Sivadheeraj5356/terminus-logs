"""Behavioral checks for the LOWESS smoother in /app.

The submitted C source is compiled by this checker with a fixed compiler command,
then driven purely through its CLI. Each case is fed as a JSON object on stdin and
the single line printed on stdout is parsed as a JSON array and compared
elementwise, with a numeric tolerance, to the reference fitted values.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

APP = "/app"
BIN_NAME = "lowess"
CORPUS = os.path.join(os.path.dirname(__file__), "corpus.jsonl")

ATOL = 1e-6
RTOL = 1e-6


def _load_corpus():
    cases = []
    with open(CORPUS, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


CASES = _load_corpus()


def _hide_corpus_for_candidate():
    """Remove corpus data before compiling or running submitted code."""
    if os.path.abspath(os.path.dirname(CORPUS)) != "/tests":
        return
    if os.path.exists(CORPUS):
        os.unlink(CORPUS)


@pytest.fixture(scope="session")
def binary():
    """Build /app/lowess.c with a checker-owned compiler command."""
    _hide_corpus_for_candidate()
    build_dir = tempfile.mkdtemp(prefix=".lowess-build-", dir=APP)
    path = os.path.join(build_dir, BIN_NAME)
    proc = subprocess.run(
        [
            "cc",
            "-O2",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-pedantic",
            "-o",
            path,
            os.path.join(APP, "lowess.c"),
            "-lm",
        ],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"cc failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    assert os.path.exists(path), f"built binary not found at {path}"
    assert os.access(path, os.X_OK), f"built binary is not executable at {path}"
    yield path
    shutil.rmtree(build_dir, ignore_errors=True)


def _run(binary, case):
    payload = json.dumps({
        "x": case["x"],
        "y": case["y"],
        "frac": case["frac"],
        "it": case["it"],
        "delta": case["delta"],
    })
    proc = subprocess.run(
        [binary],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"lowess exited {proc.returncode}; stderr={proc.stderr!r}"
    )
    return proc.stdout.strip()


def test_corpus_size():
    # Guard against a truncated or overwritten corpus.
    assert len(CASES) >= 280, f"corpus too small: {len(CASES)}"


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[
        f"{i:03d}-n{len(c['x'])}-frac{c['frac']:.3f}-it{c['it']}-d{c['delta']:.4f}"
        for i, c in enumerate(CASES)
    ],
)
def test_lowess_fit(binary, case):
    out = _run(binary, case)
    got = json.loads(out)
    expected = case["expected"]
    assert isinstance(got, list), f"output is not a JSON array: {out!r}"
    assert len(got) == len(expected), (
        f"expected {len(expected)} fitted values, got {len(got)}"
    )
    for j, (a, b) in enumerate(zip(got, expected)):
        a = float(a)
        b = float(b)
        tol = ATOL + RTOL * abs(b)
        assert abs(a - b) <= tol, (
            f"index {j}: expected {b!r}, got {a!r} "
            f"(|diff|={abs(a - b):.3e} > tol={tol:.3e})"
        )
