"""Behavioral helpers for CT PKI pytest (not collected as tests)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import ct_merkle_kernel as ctmath
from ct_pki_harness import (
    ALPHA_TRUSTED,
    BUNDLE_ALPHA,
    CTPKI,
    DISPOSITION,
    LEDGER,
    PUBLISH_EPOCH,
    SNAPSHOT,
    fresh_state,
    holdout_bundle,
    read_json,
    run_cmd,
    run_pipeline,
)


def row_for_serial(report: dict, serial: str, *, index: int = 0) -> dict:
    matches = [r for r in report["rows"] if r["serial"] == serial]
    return matches[index]


def layout_gate_ok() -> subprocess.CompletedProcess[str]:
    return run_cmd(["/app/scripts/pki_migration_bundle_gate.sh", str(BUNDLE_ALPHA)], check=False)


def layout_gate_missing_fails() -> subprocess.CompletedProcess[str]:
    missing = Path(tempfile.mkdtemp(dir=SNAPSHOT.parent))
    return run_cmd(
        ["/app/scripts/pki_migration_bundle_gate.sh", str(missing)],
        check=False,
    )


def ctpki_executable() -> bool:
    return CTPKI.is_file() and bool(CTPKI.stat().st_mode & 0o111)


def evaluate_alpha_snapshot() -> dict:
    fresh_state()
    run_cmd(
        [
            str(CTPKI),
            "attest",
            "--bundle",
            str(BUNDLE_ALPHA),
            "--snapshot",
            str(SNAPSHOT),
            "--report",
            str(DISPOSITION),
        ]
    )
    return read_json(SNAPSHOT)


def disposition_row_count() -> int:
    run_pipeline(BUNDLE_ALPHA)
    return len(read_json(DISPOSITION)["rows"])


def ledger_contract_match() -> bool:
    run_pipeline(BUNDLE_ALPHA)
    out = read_json(LEDGER)
    snap = read_json(SNAPSHOT)
    ref = ctmath.reference_evaluate_snapshot(BUNDLE_ALPHA, snap)["ledger_block"]
    return (
        out["trusted_serials"] == ref["trusted_serials"] == sorted(ALPHA_TRUSTED)
        and out["combined_digest"] == ref["combined_digest"]
    )


def disposition_snapshot_contract_match() -> bool:
    run_pipeline(BUNDLE_ALPHA)
    snap = read_json(SNAPSHOT)
    return read_json(DISPOSITION)["rows"] == ctmath.reference_evaluate_snapshot(BUNDLE_ALPHA, snap)["rows"]


def holdout_contract_match() -> bool:
    bundle = holdout_bundle()
    run_pipeline(bundle)
    out = read_json(LEDGER)
    snap = read_json(SNAPSHOT)
    ref = ctmath.reference_evaluate_snapshot(bundle, snap)["ledger_block"]
    return (
        out["trusted_serials"] == ref["trusted_serials"]
        and out["combined_digest"] == ref["combined_digest"]
        and out.get("publish_epoch", 0) == ref.get("publish_epoch", 0)
    )


def snapshot_row_digest_present() -> bool:
    snap = evaluate_alpha_snapshot()
    digest = snap.get("merkle_row_digest", "")
    return len(digest) == 64 and digest == ctmath.snapshot_row_digest(snap)


def publish_requires_snapshot() -> bool:
    fresh_state()
    run_cmd(
        [
            str(CTPKI),
            "attest",
            "--bundle",
            str(BUNDLE_ALPHA),
            "--snapshot",
            str(SNAPSHOT),
            "--report",
            str(DISPOSITION),
        ]
    )
    proc = run_cmd(
        [str(CTPKI), "publish", "--report", str(DISPOSITION), "--out", str(LEDGER)],
        check=False,
    )
    return proc.returncode != 0


def ledger_lineage_binding_match() -> bool:
    run_pipeline(BUNDLE_ALPHA)
    out = read_json(LEDGER)
    snap = read_json(SNAPSHOT)
    ref = ctmath.reference_evaluate_snapshot(BUNDLE_ALPHA, snap)["ledger_block"]
    return out["combined_digest"] == ref["combined_digest"] and out.get("publish_epoch") == ref.get("publish_epoch")


def repeat_publish_epoch() -> bool:
    run_pipeline(BUNDLE_ALPHA)
    first = read_json(LEDGER).get("publish_epoch", 0)
    run_cmd(
        [
            str(CTPKI),
            "publish",
            "--report",
            str(DISPOSITION),
            "--snapshot",
            str(SNAPSHOT),
            "--out",
            str(LEDGER),
        ]
    )
    second = read_json(LEDGER).get("publish_epoch", 0)
    return first == 1 and second == 2 and PUBLISH_EPOCH.is_file()


def snapshot_preserves_entry_order() -> bool:
    snap = evaluate_alpha_snapshot()
    bundle_order = [e["serial"] for e in ctmath.load_jsonl(BUNDLE_ALPHA / "ct_logs/b161aa7f_entries.jsonl")]
    staged = [r["serial"] for r in snap["rows"]]
    return staged == bundle_order
