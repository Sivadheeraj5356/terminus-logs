"""Shared fixtures for milestone 2 tests."""

from __future__ import annotations

import sqlite3

import pytest

BATCH_ID = "BATCH-001"
DB_PATH = "/var/lib/ops/ops.db"


@pytest.fixture(autouse=True)
def ensure_batch_verified() -> None:
    """Require M1 verification without re-running verify-ledger (avoids fixture cascades)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT chain_ok FROM ledger_verifications WHERE batch_id = ?",
        (BATCH_ID,),
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None and row[0] == 1, (
        "BATCH-001 must be verified (chain_ok=1) before milestone 2 tests"
    )
