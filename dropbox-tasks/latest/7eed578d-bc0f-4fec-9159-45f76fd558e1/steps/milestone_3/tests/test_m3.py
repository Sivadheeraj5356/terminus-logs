"""Tests for milestone 3: run scoring worker."""

from __future__ import annotations

import hmac
import math
import re
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = "/var/lib/ops/ops.db"
BATCH_ID = "BATCH-001"
JOB_ID = "JOB-20250620-001"
ACCOUNT_COUNT = 5
PREDICT_SECRET = b"prediction-hmac-key-v1-ops"
INTERCEPT = -2.5
WEIGHTS = {
    "tx_count": 0.15,
    "total_amount": 0.00001,
    "foreign_ratio": 1.8,
    "max_amount": 0.00005,
}
WORKER = Path("/app/risk_worker")
ISO_8601_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def expected_score(
    tx_count: int, total_amount: int, foreign_ratio: float, max_amount: int
) -> float:
    z = (
        INTERCEPT
        + WEIGHTS["tx_count"] * tx_count
        + WEIGHTS["total_amount"] * total_amount
        + WEIGHTS["foreign_ratio"] * foreign_ratio
        + WEIGHTS["max_amount"] * max_amount
    )
    return round(1.0 / (1.0 + math.exp(-z)), 6)


def prediction_hmac(job_id: str, account_id: str, risk_score: float) -> str:
    msg = f"{job_id}|{account_id}|{risk_score:.6f}".encode()
    return hmac.digest(PREDICT_SECRET, msg, "sha256").hex()


class TestMilestone3:
    def test_prior_milestones_persist(self) -> None:
        """M1 verification and M2 feature rows must exist before scoring."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT chain_ok FROM ledger_verifications WHERE batch_id = ?",
            (BATCH_ID,),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT COUNT(*) FROM feature_store WHERE batch_id = ?",
            (BATCH_ID,),
        )
        assert cur.fetchone()[0] == ACCOUNT_COUNT
        conn.close()

    def test_run_scoring_cli_output(self) -> None:
        """run-scoring must reset a queued job and print the exact SCORE status line."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM scoring_predictions WHERE job_id = ?", (JOB_ID,))
        conn.execute(
            "UPDATE scoring_jobs SET status = 'queued', completed_at = NULL WHERE job_id = ?",
            (JOB_ID,),
        )
        conn.commit()
        conn.close()

        proc = subprocess.run(
            [str(WORKER), "run-scoring", "--job", JOB_ID],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        expected = f"SCORE job={JOB_ID} accounts={ACCOUNT_COUNT} status=completed"
        assert proc.stdout.strip() == expected, proc.stdout

    def test_job_completed_and_predictions_signed(self) -> None:
        """Job must complete with per-account risk scores and valid prediction HMACs."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT status, completed_at FROM scoring_jobs WHERE job_id = ?",
            (JOB_ID,),
        )
        job = cur.fetchone()
        assert job is not None
        assert job[0] == "completed"
        assert job[1] is not None
        assert ISO_8601_Z.match(job[1]), job[1]

        cur.execute(
            """
            SELECT p.account_id, p.risk_score, p.prediction_hmac, p.signed_at,
                   f.tx_count, f.total_amount, f.foreign_ratio, f.max_amount
            FROM scoring_predictions p
            JOIN feature_store f
              ON f.batch_id = ? AND f.account_id = p.account_id
            WHERE p.job_id = ?
            ORDER BY p.account_id
            """,
            (BATCH_ID, JOB_ID),
        )
        rows = cur.fetchall()
        conn.close()

        assert len(rows) == ACCOUNT_COUNT
        for account_id, risk_score, pred_hmac, signed_at, tx, total, foreign, mx in rows:
            assert signed_at is not None
            assert ISO_8601_Z.match(signed_at), (account_id, signed_at)
            expected = expected_score(tx, total, foreign, mx)
            assert abs(risk_score - expected) < 1e-5, (account_id, risk_score, expected)
            assert pred_hmac == prediction_hmac(JOB_ID, account_id, expected)
