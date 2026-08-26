"""Tests for milestone 2: populate feature store."""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = "/var/lib/ops/ops.db"
BATCH_ID = "BATCH-001"
UNVERIFIED_BATCH = "UNVERIFIED-X"
LEDGER_PATH = "/app/data/ledger/batch_001.csv"
ACCOUNT_COUNT = 5
WORKER = Path("/app/risk_worker")
ISO_8601_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

EXPECTED_ACCOUNTS = {
    "a1b2c3d4e5f6": (2, 21400, 10700.0, 0.0, 12500),
    "f6e5d4c3b2a1": (2, 570000, 285000.0, 0.5, 450000),
    "9f8e7d6c5b4a": (3, 16100, 5366.666667, 0.666667, 7800),
    "deadbeefcafe": (1, 990000, 990000.0, 1.0, 990000),
    "cafebabef00d": (2, 3700, 1850.0, 0.0, 2200),
}


class TestMilestone2:
    def test_milestone_1_verification_persists(self) -> None:
        """BATCH-001 must remain verified before feature population runs."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT chain_ok FROM ledger_verifications WHERE batch_id = ?",
            (BATCH_ID,),
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None and row[0] == 1

    def test_refuses_unverified_batch(self) -> None:
        """populate-features must reject batches without chain_ok=1 verification."""
        proc = subprocess.run(
            [str(WORKER), "populate-features", "--batch", UNVERIFIED_BATCH],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, proc.stdout
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (UNVERIFIED_BATCH,),
        )
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_populate_features_cli_output(self) -> None:
        """populate-features must print the exact FEATURES status line."""
        proc = subprocess.run(
            [str(WORKER), "populate-features", "--batch", BATCH_ID],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        expected = f"FEATURES batch={BATCH_ID} accounts={ACCOUNT_COUNT}"
        assert proc.stdout.strip() == expected, proc.stdout

    def test_populate_features_accepts_ledger_flag(self) -> None:
        """populate-features must honor an explicit --ledger path."""
        proc = subprocess.run(
            [
                str(WORKER),
                "populate-features",
                "--batch",
                BATCH_ID,
                "--ledger",
                LEDGER_PATH,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        expected = f"FEATURES batch={BATCH_ID} accounts={ACCOUNT_COUNT}"
        assert proc.stdout.strip() == expected, proc.stdout

    def test_rejects_ledger_batch_id_mismatch(self, tmp_path: Path) -> None:
        """populate-features must reject ledgers whose batch_id column disagrees with --batch."""
        mismatched = tmp_path / "mixed_batch.csv"
        shutil.copy(LEDGER_PATH, mismatched)
        lines = mismatched.read_text(encoding="utf-8").splitlines()
        parts = lines[-1].split(",")
        parts[0] = "BATCH-OTHER"
        lines[-1] = ",".join(parts)
        mismatched.write_text("\n".join(lines) + "\n", encoding="utf-8")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (BATCH_ID,),
        )
        before = cur.fetchone()[0]
        conn.close()

        proc = subprocess.run(
            [
                str(WORKER),
                "populate-features",
                "--batch",
                BATCH_ID,
                "--ledger",
                str(mismatched),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, proc.stdout

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (BATCH_ID,),
        )
        after = cur.fetchone()[0]
        conn.close()
        assert after == before

    def test_populate_features_is_idempotent(self) -> None:
        """Re-running populate-features must replace rows, not duplicate them."""
        cmd = [str(WORKER), "populate-features", "--batch", BATCH_ID]
        for _ in range(2):
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode == 0, proc.stderr

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (BATCH_ID,),
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count == ACCOUNT_COUNT

    def test_feature_store_rows(self) -> None:
        """Each account row must match expected aggregates with %.6f-rounded floats."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (BATCH_ID,),
        )
        count = cur.fetchone()[0]
        assert count == ACCOUNT_COUNT

        for account_id, expected in EXPECTED_ACCOUNTS.items():
            cur.execute(
                """
                SELECT tx_count, total_amount, avg_amount, foreign_ratio, max_amount, populated_at
                FROM feature_store
                WHERE batch_id = ? AND account_id = ?
                """,
                (BATCH_ID, account_id),
            )
            row = cur.fetchone()
            assert row is not None, account_id
            tx_count, total, avg, foreign_ratio, max_amount, populated_at = row
            exp_tx, exp_total, exp_avg, exp_foreign, exp_max = expected
            assert tx_count == exp_tx and total == exp_total and max_amount == exp_max, account_id
            # Exact equality on avg/foreign_ratio is intentional: policy requires %.6f storage.
            assert avg == exp_avg, (account_id, "avg_amount", avg, exp_avg)
            assert foreign_ratio == exp_foreign, (
                account_id,
                "foreign_ratio",
                foreign_ratio,
                exp_foreign,
            )
            assert ISO_8601_Z.match(populated_at), populated_at

        conn.close()
