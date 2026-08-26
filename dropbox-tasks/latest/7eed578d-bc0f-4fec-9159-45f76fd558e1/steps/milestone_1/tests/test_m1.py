"""Tests for milestone 1: verify ledger provenance."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = "/var/lib/ops/ops.db"
BATCH_ID = "BATCH-001"
LEDGER_PATH = "/app/data/ledger/batch_001.csv"
SECRET_PATH = Path("/app/config/hmac_secret.txt")
LEDGER_ROWS = 11  # genesis + 10 transactions
TAMPER_BATCH = "BATCH-TAMPER"
WORKER = Path("/app/risk_worker")
ISO_8601_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def genesis_hmac(secret: bytes, batch_id: str) -> str:
    return hmac.new(secret, f"GENESIS|{batch_id}".encode(), hashlib.sha256).hexdigest()


def chain_hmac(secret: bytes, prev: str, payload: str) -> str:
    return hmac.new(secret, f"{prev}|{payload}".encode(), hashlib.sha256).hexdigest()


def write_signed_ledger(
    path: Path,
    batch_id: str,
    secret: bytes,
    rows: list[tuple[str, int, str, str]],
) -> int:
    """Write a signed ledger CSV; returns total row count including genesis."""
    prev = genesis_hmac(secret, batch_id)
    out_rows: list[dict[str, str | int]] = [
        {
            "batch_id": batch_id,
            "sequence": 0,
            "pan_hash": "GENESIS",
            "amount_cents": 0,
            "merchant_code": "0000",
            "country": "XX",
            "hmac": prev,
        }
    ]
    for seq, (pan, amount, merchant, country) in enumerate(rows, start=1):
        payload = f"{pan}|{amount}|{merchant}|{country}"
        digest = chain_hmac(secret, prev, payload)
        out_rows.append(
            {
                "batch_id": batch_id,
                "sequence": seq,
                "pan_hash": pan,
                "amount_cents": amount,
                "merchant_code": merchant,
                "country": country,
                "hmac": digest,
            }
        )
        prev = digest

    fieldnames = [
        "batch_id",
        "sequence",
        "pan_hash",
        "amount_cents",
        "merchant_code",
        "country",
        "hmac",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(out_rows)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return len(out_rows)


def run_verify(batch_id: str, ledger: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(WORKER),
            "verify-ledger",
            "--batch",
            batch_id,
            "--ledger",
            str(ledger),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def table_counts() -> tuple[int, int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM feature_store")
    features = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scoring_predictions")
    predictions = cur.fetchone()[0]
    conn.close()
    return features, predictions


def flip_last_hex_char(digest: str) -> str:
    last = digest[-1]
    replacement = "a" if last != "a" else "b"
    return digest[:-1] + replacement


class TestMilestone1:
    def test_worker_build_artifacts(self) -> None:
        """Agent must compile risk_worker from flat /app C sources via Makefile."""
        assert WORKER.exists(), f"{WORKER} must be built via Makefile"
        assert WORKER.stat().st_mode & 0o111, f"{WORKER} must be executable"

        makefile = Path("/app/Makefile")
        assert makefile.exists(), "Makefile must exist at /app/Makefile"
        makefile_text = makefile.read_text(encoding="utf-8")
        assert "risk_worker" in makefile_text, "Makefile must build risk_worker"

        c_files = list(Path("/app").glob("*.c"))
        assert len(c_files) > 0, "C source files must exist under /app"

    def test_reference_binary_not_shipped(self) -> None:
        """Reference oracle binary must not be present in the agent image."""
        assert not Path("/usr/share/tbench-ref/risk_worker").exists(), (
            "Reference worker binary must not be available in the agent image"
        )

    def test_verify_ledger_cli_output(self) -> None:
        """verify-ledger must print the exact VERIFY status line on success."""
        proc = run_verify(BATCH_ID, LEDGER_PATH)
        assert proc.returncode == 0, proc.stderr
        expected = f"VERIFY batch={BATCH_ID} rows={LEDGER_ROWS} chain=OK"
        assert proc.stdout.strip() == expected, proc.stdout

    def test_ledger_verifications_row(self) -> None:
        """Successful verify must persist row_count, chain_ok, and verified_at."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT row_count, chain_ok, verified_at FROM ledger_verifications WHERE batch_id = ?",
            (BATCH_ID,),
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None, "ledger_verifications must contain BATCH-001"
        assert row[0] == LEDGER_ROWS
        assert row[1] == 1
        assert row[2] is not None
        assert ISO_8601_Z.match(row[2]), row[2]

    def test_verify_ledger_reads_secret_from_config(self, tmp_path: Path) -> None:
        """HMAC verification must use the live secret from /app/config/hmac_secret.txt."""
        original_secret = SECRET_PATH.read_text(encoding="utf-8")
        alt_batch = "BATCH-ALT-SECRET"
        alt_secret = b"alt-test-key-for-verify"
        alt_ledger = tmp_path / "alt_secret_batch.csv"

        try:
            SECRET_PATH.write_text("alt-test-key-for-verify\n", encoding="utf-8")
            row_count = write_signed_ledger(
                alt_ledger,
                alt_batch,
                alt_secret,
                [("abc123def456", 5000, "M100", "US")],
            )
            proc = run_verify(alt_batch, alt_ledger)
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == (
                f"VERIFY batch={alt_batch} rows={row_count} chain=OK"
            )
        finally:
            SECRET_PATH.write_text(original_secret, encoding="utf-8")

        proc = run_verify(BATCH_ID, LEDGER_PATH)
        assert proc.returncode == 0, proc.stderr

    def test_rejects_cli_batch_mismatch(self) -> None:
        """--batch must match every CSV batch_id column and anchor genesis."""
        proc = run_verify("BATCH-WRONG", LEDGER_PATH)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

    def test_rejects_gapped_sequence_numbers(self, tmp_path: Path) -> None:
        """Non-contiguous sequence numbers must fail verification."""
        tampered = tmp_path / "gapped_sequence.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        parts = lines[6].split(",")
        parts[1] = "99"
        lines[6] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        proc = run_verify(BATCH_ID, tampered)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

    def test_failed_verify_does_not_insert_verification_row(
        self, tmp_path: Path
    ) -> None:
        """Failed verify must write no ledger_verifications row for the batch."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ledger_verifications WHERE batch_id = ?",
            (TAMPER_BATCH,),
        )
        before = cur.fetchone()[0]
        conn.close()

        tampered = tmp_path / "bad_new_batch.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        parts = lines[-1].split(",")
        parts[-1] = flip_last_hex_char(parts[-1])
        lines[-1] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        proc = run_verify(TAMPER_BATCH, tampered)
        assert proc.returncode != 0, proc.stdout

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ledger_verifications WHERE batch_id = ?",
            (TAMPER_BATCH,),
        )
        after = cur.fetchone()[0]
        conn.close()
        assert after == before

    def test_failed_verify_does_not_overwrite_existing_success(
        self, tmp_path: Path
    ) -> None:
        """Failed verify on BATCH-001 must not overwrite an existing chain_ok=1 row."""
        proc = run_verify(BATCH_ID, LEDGER_PATH)
        assert proc.returncode == 0, proc.stderr

        tampered = tmp_path / "bad_same_batch.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        parts = lines[-1].split(",")
        parts[-1] = flip_last_hex_char(parts[-1])
        lines[-1] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        proc = run_verify(BATCH_ID, tampered)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT row_count, chain_ok FROM ledger_verifications WHERE batch_id = ?",
            (BATCH_ID,),
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None, "prior successful verification row must remain"
        assert row[0] == LEDGER_ROWS
        assert row[1] == 1, "must not overwrite chain_ok=1 with failure"

    def test_rejects_plausible_wrong_hmac_on_last_row(self, tmp_path: Path) -> None:
        """Single-bit last-row HMAC corruption must fail without touching BATCH-001."""
        tampered = tmp_path / "bad_last_hmac.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        parts = lines[-1].split(",")
        parts[-1] = flip_last_hex_char(parts[-1])
        lines[-1] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        proc = run_verify(TAMPER_BATCH, tampered)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT chain_ok FROM ledger_verifications WHERE batch_id = ?",
            (BATCH_ID,),
        )
        row = cur.fetchone()
        conn.close()
        if row is not None:
            assert row[0] == 1, "tamper tests must not corrupt BATCH-001 verification"

    def test_rejects_mid_chain_hmac_mismatch(self, tmp_path: Path) -> None:
        """Mid-chain HMAC corruption must break verification."""
        tampered = tmp_path / "bad_mid_chain.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        mid_idx = len(lines) // 2
        parts = lines[mid_idx].split(",")
        parts[-1] = flip_last_hex_char(parts[-1])
        lines[mid_idx] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        proc = run_verify(TAMPER_BATCH, tampered)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

    def test_rejects_tampered_amount_without_hmac_update(self, tmp_path: Path) -> None:
        """Amount tampering without HMAC update must fail and leave other tables untouched."""
        tampered = tmp_path / "bad_amount.csv"
        shutil.copy(LEDGER_PATH, tampered)
        lines = tampered.read_text(encoding="utf-8").splitlines()
        parts = lines[-1].split(",")
        parts[3] = str(int(parts[3]) + 1)
        lines[-1] = ",".join(parts)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

        features_before, predictions_before = table_counts()
        proc = run_verify(TAMPER_BATCH, tampered)
        assert proc.returncode != 0, proc.stdout
        assert "chain=OK" not in proc.stdout

        features_after, predictions_after = table_counts()
        assert features_after == features_before
        assert predictions_after == predictions_before

        proc = run_verify(BATCH_ID, LEDGER_PATH)
        assert proc.returncode == 0, proc.stderr
