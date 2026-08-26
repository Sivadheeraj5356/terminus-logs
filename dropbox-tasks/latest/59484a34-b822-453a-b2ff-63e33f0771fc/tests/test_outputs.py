"""Pytest entry — CT PKI trust evidence reconstructor behavioral checks."""

from __future__ import annotations

import ctpki_contract as ctref
import ct_merkle_kernel as ctmath
import ct_ledger_probe as H
from ct_pki_harness import (
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


def test_ctwitness_deliverable_paths():
    """Full attest and publish pipeline creates all three instruction deliverable paths."""
    run_pipeline(BUNDLE_ALPHA)
    assert SNAPSHOT.is_file()
    assert DISPOSITION.is_file()
    assert LEDGER.is_file()
    assert H.PUBLISH_EPOCH.is_file()
    assert SNAPSHOT.parent.is_dir()
    assert str(SNAPSHOT.parent) == "/app/state/pki-evidence"
    assert str(PUBLISH_EPOCH) == "/app/state/pki-evidence/publish_epoch.json"
    assert str(SNAPSHOT) == "/app/state/pki-evidence/ct_merkle_snapshot.json"
    assert str(DISPOSITION) == "/app/state/pki-evidence/disposition_matrix.json"
    assert str(LEDGER) == "/app/output/published_ct_ledger.json"


def test_ctwitness_01():
    """Migration gate accepts bundle-migration-alpha per migration-bundle-contract.md."""
    proc = H.layout_gate_ok()
    assert proc.returncode == 0
    assert "pki_migration_bundle_gate: ok" in proc.stdout


def test_ctpkib8f_02():
    """Migration gate rejects absent bundle roots."""
    assert H.layout_gate_missing_fails().returncode != 0


def test_ctpkib8f_03():
    """ctpki binary must exist at /app/bin/ctpki."""
    assert H.ctpki_executable()


def test_ctwitness_04():
    """Attest materializes /app/state/pki-evidence/ct_merkle_snapshot.json with eight certificate rows from the ingest pass."""
    snap = H.evaluate_alpha_snapshot()
    assert SNAPSHOT.is_file()
    assert str(SNAPSHOT) == "/app/state/pki-evidence/ct_merkle_snapshot.json"
    assert snap["bundle_id"] == "bundle-migration-alpha-7c2"
    assert len(snap["rows"]) == 8


def test_ctpkib8f_05():
    """Staging preserves ct_logs/entries.jsonl order."""
    assert H.snapshot_preserves_entry_order()


def test_ctpkib8f_06():
    """Staging row for legacy backup retains spaced filename."""
    snap = H.evaluate_alpha_snapshot()
    legacy = next(r for r in snap["rows"] if r["serial"] == "SER-LEGACY")
    assert legacy["filename"] == "legacy backup.json"


def test_ctwitness_07():
    """Attest writes /app/state/pki-evidence/disposition_matrix.json with eight scored rows."""
    assert H.disposition_row_count() == 8
    assert DISPOSITION.is_file()
    assert str(DISPOSITION) == "/app/state/pki-evidence/disposition_matrix.json"


def test_ctpkib8f_08():
    """SER-REVOKED rejected with revoked reason."""
    run_pipeline(BUNDLE_ALPHA)
    row = H.row_for_serial(read_json(DISPOSITION), "SER-REVOKED")
    assert row["disposition"] == "rejected" and row["reason"] == "revoked"


def test_ctpkib8f_09():
    """SER-WTREE rejected for wrong_tree_size."""
    run_pipeline(BUNDLE_ALPHA)
    row = H.row_for_serial(read_json(DISPOSITION), "SER-WTREE")
    assert row["reason"] == "wrong_tree_size"


def test_ctpkib8f_10():
    """Duplicate SER-DUP older row rejected duplicate_serial."""
    run_pipeline(BUNDLE_ALPHA)
    rows = [r for r in read_json(DISPOSITION)["rows"] if r["serial"] == "SER-DUP"]
    assert rows[0]["disposition"] == "trusted" and rows[1]["reason"] == "duplicate_serial"


def test_ctpkib8f_11():
    """SER-STALE rejected for stale_sth."""
    run_pipeline(BUNDLE_ALPHA)
    assert H.row_for_serial(read_json(DISPOSITION), "SER-STALE")["reason"] == "stale_sth"


def test_ctpkib8f_12():
    """SER-NOPROOF needs_review missing_proof."""
    run_pipeline(BUNDLE_ALPHA)
    row = H.row_for_serial(read_json(DISPOSITION), "SER-NOPROOF")
    assert row["disposition"] == "needs_review" and row["reason"] == "missing_proof"


def test_ctpkib8f_13():
    """SER-BADROOT rejected untrusted_root."""
    run_pipeline(BUNDLE_ALPHA)
    assert H.row_for_serial(read_json(DISPOSITION), "SER-BADROOT")["reason"] == "untrusted_root"


def test_ctpkib8f_14():
    """Merkle reference verifies alpha SER-LEGACY proof path."""
    entry = ctmath.load_jsonl(BUNDLE_ALPHA / "ct_logs/b161aa7f_entries.jsonl")[0]
    proof = ctmath.load_proofs(BUNDLE_ALPHA)[f"{entry['serial']}:{entry['leaf_index']}"]
    sth = read_json(BUNDLE_ALPHA / "ct_logs/sth.json")
    assert ctmath.reference_merkle_path(entry["leaf_hash"], entry["leaf_index"], proof["path"], sth["root_hash"])


def test_ctpkib8f_15():
    """Manifest digest helper accepts alpha bundle.sha256 rows."""
    assert ctref.manifest_digest_ok(BUNDLE_ALPHA)


def test_ctwitness_16():
    """Publish writes /app/output/published_ct_ledger.json after disposition scoring."""
    run_pipeline(BUNDLE_ALPHA)
    assert LEDGER.is_file()
    assert str(LEDGER) == "/app/output/published_ct_ledger.json"
    assert read_json(LEDGER)["bundle_id"] == "bundle-migration-alpha-7c2"


def test_ctpkib8f_17():
    """Ledger export matches contract for alpha snap order."""
    assert H.ledger_contract_match()


def test_ctpkib8f_18():
    """Disposition rows match contract for snap order."""
    assert H.disposition_snapshot_contract_match()


def test_ctpkib8f_19():
    """Verifier holdout migration bundle under verifier-fixtures staging is present for attest."""
    bundle = holdout_bundle()
    assert bundle.is_dir() and (bundle / "bundle_meta.json").is_file()


def test_ctpkib8f_20():
    """Holdout verifier-fixtures migration export matches independent reference contract."""
    assert H.holdout_contract_match()


def test_ctpkib8f_21():
    """trusted_count is two for bundle-migration-alpha."""
    run_pipeline(BUNDLE_ALPHA)
    assert read_json(LEDGER)["trusted_count"] == 2


def test_ctpkib8f_22():
    """Trust scores follow trust-disposition-scoring.md for trusted rows."""
    run_pipeline(BUNDLE_ALPHA)
    for row in read_json(DISPOSITION)["rows"]:
        if row["disposition"] == "trusted":
            assert row["trust_score"] == 100


def test_ctpkib8f_23():
    """Needs review serials appear in ledger needs_review_serials only."""
    run_pipeline(BUNDLE_ALPHA)
    ledger = read_json(LEDGER)
    assert "SER-NOPROOF" in ledger["needs_review_serials"]
    assert "SER-NOPROOF" not in ledger["trusted_serials"]


def test_ctpkib8f_24():
    """Evaluate subprocess exits zero on alpha bundle."""
    fresh_state()
    proc = run_cmd(
        [
            str(CTPKI),
            "attest",
            "--bundle",
            str(BUNDLE_ALPHA),
            "--snapshot",
            str(SNAPSHOT),
            "--report",
            str(DISPOSITION),
        ],
        check=False,
    )
    assert proc.returncode == 0


def test_ctwitness_25():
    """Staging snapshot carries merkle_row_digest over attest row order."""
    assert H.snapshot_row_digest_present()


def test_ctpkib8f_26():
    """publish subcommand rejects missing --snapshot flag."""
    assert H.publish_requires_snapshot()


def test_ctpkib8f_27():
    """Ledger combined_digest binds snapshot merkle_row_digest per publish-seal-lineage.md."""
    assert H.ledger_lineage_binding_match()


def test_ctwitness_28():
    """Repeat publish increments publish_epoch and persists publish_epoch.json."""
    assert H.repeat_publish_epoch()


def test_ctpkib8f_29():
    """Holdout export binds lineage digest from verifier-fixtures snapshot."""
    bundle = holdout_bundle()
    run_pipeline(bundle)
    out = read_json(LEDGER)
    snap = read_json(SNAPSHOT)
    ref = ctmath.reference_evaluate_snapshot(bundle, snap)["ledger_block"]
    assert out["combined_digest"] == ref["combined_digest"]


def test_ctpkib8f_30():
    """Published ledger carries publish_epoch field after first publish."""
    run_pipeline(BUNDLE_ALPHA)
    assert read_json(LEDGER)["publish_epoch"] == 1


def test_ctwitness_31():
    """State directory hosts publish_epoch.json after publish."""
    run_pipeline(BUNDLE_ALPHA)
    assert PUBLISH_EPOCH.is_file()
    assert read_json(PUBLISH_EPOCH)["epoch"] == 1
