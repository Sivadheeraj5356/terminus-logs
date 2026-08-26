"""Behavioral verifier for the LCG keystream-recovery task.

The attack is graded only by executed behavior: this module builds the candidate
Rust program at /app, runs it on a deterministic family of fresh planted
challenges under a per-run time budget, and compares its recovered plaintext
byte-exact against the planted flag, which is also re-derived by an independent
reference (oracle_lcg.py). Candidate source is never inspected. A window-
extension metamorphic check confirms the recovery tracks the keystream boundary
rather than a fixed index.
"""

import importlib.util
import os
import subprocess

import pytest

APP = os.environ.get("LCG_APP", "/app")
BINARY = os.path.join(APP, "lcgrecover")
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_TIMEOUT = 20


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(HERE, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load("gen")
oracle = _load("oracle_lcg")

INSTANCES = gen.instances()
PAIRS = gen.metamorphic_pairs()


@pytest.fixture(scope="session")
def binary():
    proc = subprocess.run(
        ["make", "-C", APP], capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0 and os.path.exists(BINARY), (
        "candidate failed to build:\n" + proc.stdout + proc.stderr
    )
    return BINARY


def _run(binary, text, tmp_path):
    ch = tmp_path / "challenge.txt"
    ch.write_text(text)
    try:
        proc = subprocess.run(
            [binary, str(ch)], capture_output=True, timeout=RUN_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return b"<TIMEOUT>"
    return proc.stdout.rstrip(b"\n")


@pytest.mark.parametrize("name,text,flag", INSTANCES, ids=[i[0] for i in INSTANCES])
def test_recover(binary, tmp_path, name, text, flag):
    """Candidate recovers the planted flag, which the independent reference confirms."""
    assert oracle.solve_text(text) == flag, name + ": challenge is malformed"
    got = _run(binary, text, tmp_path)
    assert got == flag, name + ": expected " + repr(flag) + " got " + repr(got)


@pytest.mark.parametrize(
    "name,base_text,ext_text,flag", PAIRS, ids=[p[0] for p in PAIRS]
)
def test_window_extension_metamorphic(
    binary, tmp_path, name, base_text, ext_text, flag
):
    """Extending the published run moves the keystream boundary but not the recovered flag."""
    got_base = _run(binary, base_text, tmp_path)
    got_ext = _run(binary, ext_text, tmp_path)
    assert got_base == flag, name + ": base recovery wrong"
    assert got_ext == flag, name + ": extended-window recovery wrong"


def test_case_floor():
    """The executed battery clears the behavioral floor of 60 fresh challenges."""
    assert len(INSTANCES) >= 60
