"""Behavioural verifier for the `mangle` candidate generator.

The C program under test is built from the agent's source in ``/app`` and run
as a black box: it is given a one-rule file and a one-word file and must print
the candidate the rule produces for that word, byte for byte, followed by a
newline -- or nothing when the pair is rejected or the rule is malformed. Each
output is compared against a hidden reference corpus produced by the reference
rule engine. The corpus spans independent families (multi-function chaining,
reject functions, out-of-range positional edits, the memory functions,
base-36/escape position arguments, and buffer-tail scanning) -- each a corner an
independent implementation can get wrong.
"""

import glob
import json
import os
import subprocess
import tempfile

import pytest

APP_DIR = os.environ.get("APP_DIR", "/app")
CORPUS = os.path.join(os.path.dirname(__file__), "corpus.json")


@pytest.fixture(scope="session")
def binary():
    srcs = sorted(glob.glob(os.path.join(APP_DIR, "src", "*.c")))
    assert srcs, "no C sources found under /app/src"
    out = os.path.join(tempfile.mkdtemp(prefix="mangle_build_"), "mangle")
    proc = subprocess.run(
        ["cc", "-O2", "-std=c11", "-o", out, *srcs],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, (
        "build failed (rc=%d)\nstdout:\n%s\nstderr:\n%s"
        % (proc.returncode, proc.stdout, proc.stderr)
    )
    assert os.path.exists(out), "build reported success but binary is missing"
    return out


def _load():
    with open(CORPUS) as f:
        data = json.load(f)
    recs = data["records"]
    assert recs, "empty corpus"
    return recs


RECORDS = _load()


def _run(binary, rule, word):
    """Run `binary rulefile wordfile` on a single pair; return raw stdout."""
    d = tempfile.mkdtemp(prefix="mangle_case_")
    rp = os.path.join(d, "rules")
    wp = os.path.join(d, "words")
    with open(rp, "wb") as f:
        f.write(rule.encode("latin-1") + b"\n")
    with open(wp, "wb") as f:
        f.write(word.encode("latin-1") + b"\n")
    proc = subprocess.run([binary, rp, wp], capture_output=True, timeout=30)
    assert proc.returncode == 0, (
        "non-zero exit %d for rule=%r word=%r: %r"
        % (proc.returncode, rule, word, proc.stderr[:200])
    )
    return proc.stdout


@pytest.mark.parametrize(
    "rec",
    RECORDS,
    ids=["%s:%d" % (r["family"], i) for i, r in enumerate(RECORDS)],
)
def test_candidate(binary, rec):
    rule = rec["rule"]
    word = rec["word"]
    got = _run(binary, rule, word)
    if rec["expected"] is None:
        assert got == b"", (
            "rule=%r word=%r should emit no candidate, got %r"
            % (rule, word, got)
        )
    else:
        want = bytes.fromhex(rec["expected"]) + b"\n"
        assert got == want, (
            "rule=%r word=%r\n  got : %r\n  want: %r" % (rule, word, got, want)
        )
