"""Pytest fixtures for CT PKI trust evidence verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_VS = _TESTS / "verifier-support"
if str(_VS) not in sys.path:
    sys.path.insert(0, str(_VS))

fresh_state = __import__("ct_pki_harness").fresh_state
stage_holdout_bundle = __import__("ct_pki_harness").stage_holdout_bundle


@pytest.fixture(scope="session", autouse=True)
def _stage_holdout_bundle() -> None:
    stage_holdout_bundle(_TESTS)


@pytest.fixture(autouse=True)
def _reset_outputs() -> None:
    fresh_state()
