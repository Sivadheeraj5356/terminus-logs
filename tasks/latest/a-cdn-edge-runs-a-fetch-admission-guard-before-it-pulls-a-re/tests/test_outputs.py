"""Behavioral verifier for the edge fetch-admission gate.

The program under test is the Go source at ``/app`` (entry point ``main.go``,
built into the ``fetch_gate`` binary). It reads one JSON object per line on
standard input, each of the form
``{"source_list": "...", "url": "...", "origin": "..."}``, and writes one line
per input to standard output containing ``ADMIT`` or ``BLOCK`` in the same
order, following the Content-Security-Policy Level 3 source-list URL-matching
algorithm.

Each case in ``corpus.json`` is an independent, discriminating decision: the
expected label was produced by a reference model of the CSP3 matching
algorithm. A naive matcher admits some bypass URLs and blocks some legitimate
ones, so it fails a distributed slice of the cases; a correct matcher passes
all of them. Cases are scored per-case so a partial implementation still scores
on the families it handles.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

APP = "/app"
BIN_NAME = "fetch_gate"
CORPUS = os.path.join(os.path.dirname(__file__), "corpus.json")
BUILD_TIMEOUT_SEC = 300
RUN_TIMEOUT_SEC = 120


def _load():
    with open(CORPUS, encoding="utf-8") as f:
        return json.load(f)


CASES = _load()


def _build():
    """Compile the candidate program from /app source into a temp binary.

    A private build cache/HOME keeps the compile hermetic and independent of
    the read-only /app layout.
    """
    go = shutil.which("go") or "/usr/local/go/bin/go"
    tmp = tempfile.mkdtemp(prefix="fetchgate-build-")
    binary = os.path.join(tmp, BIN_NAME)
    env = dict(os.environ)
    env["HOME"] = tmp
    env["GOCACHE"] = os.path.join(tmp, "gocache")
    env["GOPATH"] = os.path.join(tmp, "gopath")
    env["GOFLAGS"] = "-mod=mod"
    r = subprocess.run(
        [go, "build", "-o", binary, "."],
        cwd=APP,
        capture_output=True,
        text=True,
        env=env,
        timeout=BUILD_TIMEOUT_SEC,
    )
    assert r.returncode == 0, (
        f"go build failed (exit {r.returncode}):\n{r.stdout}\n{r.stderr}")
    assert os.path.exists(binary), "build reported success but no binary produced"
    return binary


def _run_all():
    """Feed every case (one JSON object per line) and collect the verdicts."""
    binary = _build()
    stdin = "".join(json.dumps(c["input"]) + "\n" for c in CASES)
    r = subprocess.run(
        [binary],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SEC,
    )
    assert r.returncode == 0, f"program exited nonzero: {r.stderr}"
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() != ""]
    return lines


@pytest.fixture(scope="session")
def verdicts():
    return _run_all()


def test_verdict_count(verdicts):
    """One verdict line is produced for every input case."""
    assert len(verdicts) == len(CASES), (
        f"expected {len(CASES)} verdicts, got {len(verdicts)}")


def test_verdict_vocabulary(verdicts):
    """Every verdict is exactly ADMIT or BLOCK."""
    bad = [i for i, v in enumerate(verdicts) if v not in ("ADMIT", "BLOCK")]
    assert not bad, f"non-ADMIT/BLOCK verdict at indices: {bad[:5]}"


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_case(verdicts, idx):
    """Each admission decision matches the CSP3 reference for that case."""
    c = CASES[idx]
    want = c["expected"]
    got = verdicts[idx] if idx < len(verdicts) else None
    assert got == want, (
        f"case[{idx}] source_list={c['input']['source_list']!r} "
        f"url={c['input']['url']!r} origin={c['input']['origin']!r}: "
        f"expected {want}, got {got}")
