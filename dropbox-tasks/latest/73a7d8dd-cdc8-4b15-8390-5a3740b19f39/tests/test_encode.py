import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import encode_lib as lib


@pytest.mark.parametrize("label,n,amps", lib.all_specs())
def test_prepare_distribution(label, n, amps):
    """Emitted circuit prepares the target amplitudes exactly, using only ry and cx within the budget."""
    ok, cases, reason = lib.check_one(n, amps)
    assert ok, "%s: %s" % (label, reason)
    assert cases == (1 << n) + 3


def test_metamorphic_reverse():
    """A distribution and its reverse both prepare correctly under the qubit-flip relation."""
    ok, cases, reason = lib.check_metamorphic_reverse()
    assert ok, reason
    assert cases == 3


def test_total_case_floor():
    """The full evaluation executes at least sixty semantic sub-checks (L2
    distance, CX budget, gate legality, and per-amplitude equality across all
    16 distributions plus the metamorphic-reverse relation), guarding against a
    silent reduction in coverage."""
    r, total, msg = lib.evaluate()
    assert r == 1, msg
    assert total >= 60
