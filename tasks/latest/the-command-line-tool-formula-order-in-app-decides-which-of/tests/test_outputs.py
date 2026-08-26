"""Acceptance tests for the /app formula-order comparator.

The binary is rebuilt from the /app sources, then run once per reference pair.
Each pair is checked on its own so that a single wrong rule shows up as its own
failure instead of collapsing the whole suite.
"""

import json
import os
import shutil
import subprocess

import pytest

APP = "/app"
CORPUS_PATH = os.path.join(os.path.dirname(__file__), "corpus.json")

with open(CORPUS_PATH, encoding="utf-8") as fh:
    CASES = json.load(fh)


def _go() -> str:
    for cand in ("go", "/usr/local/bin/go", "/usr/local/go/bin/go"):
        found = shutil.which(cand) or (cand if os.path.exists(cand) else None)
        if found:
            return found
    return "go"


def _build_env() -> dict:
    env = dict(os.environ)
    # Use a cache of our own so a build done earlier by a different user can
    # never leave unwritable entries behind.
    env["GOCACHE"] = "/tmp/gocache-tests"
    env["GOPATH"] = "/tmp/gopath-tests"
    env["GOFLAGS"] = "-buildvcs=false"
    if not env.get("HOME"):
        env["HOME"] = "/tmp"
    env["PATH"] = env.get("PATH", "") + ":/usr/local/go/bin:/usr/local/bin"
    return env


@pytest.fixture(scope="session")
def outputs():
    """Build the comparator from /app and collect its answer for every pair."""
    binary = "/tmp/formula-order-verify"
    build = subprocess.run(
        [_go(), "build", "-buildvcs=false", "-o", binary, "./cmd/formula-order"],
        cwd=APP,
        env=_build_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert build.returncode == 0, f"go build failed:\n{build.stdout}\n{build.stderr}"

    results = {}
    for case in CASES:
        proc = subprocess.run(
            [binary, case["a"], case["b"]],
            capture_output=True,
            text=True,
            timeout=15,
        )
        results[case["id"]] = (proc.returncode, proc.stdout.strip())
    return results


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['fam']}-{c['id']}")
def test_ordering(case, outputs):
    """The comparator must rank each reference pair exactly as the catalog does."""
    rc, got = outputs[case["id"]]
    assert rc == 0, f"formula-order {case['a']!r} {case['b']!r} exited {rc}"
    assert got == str(case["c"]), (
        f"formula-order {case['a']!r} {case['b']!r} = {got!r}, expected {case['c']}"
    )
