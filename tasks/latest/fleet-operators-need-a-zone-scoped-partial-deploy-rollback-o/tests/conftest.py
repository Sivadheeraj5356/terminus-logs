"""Verifier bootstrap — rebuild rollbackctl from Go sources before behavioral tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from test_outputs import PATH_ROLLBACK_COMPLETE, PATH_RUN_LEDGER, _rebuild_ctl


@pytest.fixture(autouse=True, scope="session")
def verifier_bootstrap() -> None:
    _rebuild_ctl()


@pytest.fixture(autouse=True)
def isolate_apply_run_state() -> None:
    """Reset per-apply run artifacts before each test.

    capture_sequence is a monotonic counter in truth-ledger.json and the apply
    replay guard keys on rollback-run-ledger.json. Both persist on disk across
    tests, so a run-ledger left by an earlier apply (or a capture_sequence reset
    by a test that deletes truth-ledger.json) can spuriously block a later apply
    for any implementation that re-validates capture_sequence. Clearing these two
    transient markers before every test makes each apply outcome depend only on
    the pipeline the test builds itself, not on cross-test state.
    """
    for path in (PATH_RUN_LEDGER, PATH_ROLLBACK_COMPLETE):
        Path(path).unlink(missing_ok=True)
