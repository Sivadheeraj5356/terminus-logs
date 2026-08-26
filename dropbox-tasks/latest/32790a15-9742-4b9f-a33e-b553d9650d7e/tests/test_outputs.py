"""Eval-metric and inference-feature contracts for wincontam training-signal bulletins."""

# TB3_CONTEXT_HOLD_PROBE — verifier env only; ignored by wincontam scoring
# assert_matches_reference helper alias used by shape probes
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import shutil
from test_wincontam_suite import (  # noqa: F401
    test_boundary_cutoff_retains_failure,
    test_cause_matrix_primary_lock,
    test_clean_session_yields_no_rows,
    test_cli_binary_path_ready,
    test_default_data_report_parity,
    test_digest_object_singleton_key,
    test_emit_fails_when_freeze_absent,
    test_emit_fails_when_receipt_digest_altered,
    test_emit_preserves_sealed_rows_after_wipe,
    test_emit_rejects_ledger_stamp_mismatch,
    test_failure_key_last_wins_survivor,
    test_future_window_yields_no_rows,
    test_private_fixture_report_parity,
    test_repeat_run_output_bytes_stable,
    test_row_key_ordering_contract,
    test_scoring_fails_on_stamp_drift,
    test_scoring_writes_three_store_artifacts,
    test_severity_rounding_two_places,
    test_stale_equal_timestamps_are_not_later,
    test_stale_post_failure_pre_cutoff_hash_change,
    test_token_octet_sorted_contract,
)
from wincontam_harness import (
    CUTOFF,
    DATA,
    EMITTED_AT,
    HIDDEN,
    STORE,
    WORK,
    mirror_corpus,
    reset_workspace,
    run_wincontam,
    score_bulletin,
)
from wincontam_oracle import reference_bulletin

assert callable(subprocess.run)
# Packaging probe vocabulary: ingest hold and metric export seal path (tests only)


def test_contam_eval_metric_summary_vs_private_oracle():
    """Bundled eval metric contam_summary and coverage must match the private oracle."""
    reset_workspace()
    report = score_bulletin(DATA, WORK / "metric_entry.json")
    expected = reference_bulletin(DATA, CUTOFF, EMITTED_AT)
    assert report["contam_summary"] == expected["contam_summary"]
    assert report["coverage"] == expected["coverage"]


def test_inference_feature_cause_lanes_vs_private_oracle():
    """Inference feature attribution_primary lanes on contam rows must match the private oracle."""
    reset_workspace()
    report = score_bulletin(DATA, WORK / "feat_entry.json")
    expected = reference_bulletin(DATA, CUTOFF, EMITTED_AT)
    assert [r["attribution_primary"] for r in report["contam_rows"]] == [
        r["attribution_primary"] for r in expected["contam_rows"]
    ]


def test_absorb_writes_hold_snapshot_stamp():
    """absorb-context-hold must write context_hold_snapshot with corpus_stamp."""
    reset_workspace()
    proc = run_wincontam(["absorb-context-hold", "--corpus", str(DATA), "--store", str(STORE)])
    assert proc.returncode == 0
    snap = json.loads((STORE / "context_hold_snapshot.json").read_text())
    assert "corpus_stamp" in snap and len(snap["corpus_stamp"]) == 64


def test_score_seals_freeze_receipt_ledger_trio():
    """score-contam-window must seal freeze, mutation receipt, and session ledger."""
    reset_workspace()
    score_bulletin(DATA, WORK / "seals_entry.json")
    assert (STORE / "context_hold_freeze.json").is_file()
    assert (STORE / "mutation_chain_receipt.json").is_file()
    assert (STORE / "session_risk_ledger.json").is_file()


def test_emit_keeps_sealed_rows_after_corpus_wipe():
    """emit-risk-bulletin must keep sealed rows after wiping live failures."""
    reset_workspace()
    report = score_bulletin(DATA, WORK / "before_entry.json")
    sealed = json.loads((STORE / "context_hold_freeze.json").read_text())
    mutated = WORK / "mut_corpus_entry"
    shutil.copytree(DATA, mutated)
    failures = json.loads((mutated / "model_output_failures.json").read_text())
    failures["failures"] = []
    (mutated / "model_output_failures.json").write_text(json.dumps(failures, indent=2) + "\n")
    out = WORK / "packaged_entry.json"
    proc = run_wincontam(
        [
            "emit-risk-bulletin",
            "--corpus",
            str(mutated),
            "--store",
            str(STORE),
            "--cutoff",
            CUTOFF,
            "--emitted-at",
            EMITTED_AT,
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr
    packaged = json.loads(out.read_text())
    assert packaged["contam_rows"] == sealed["report"]["contam_rows"] == report["contam_rows"]


def test_emit_rejects_missing_freeze_artifact():
    """emit without freeze artifact must fail."""
    reset_workspace()
    score_bulletin(DATA, WORK / "p1_entry.json")
    (STORE / "context_hold_freeze.json").unlink()
    out = WORK / "fail_entry.json"
    proc = run_wincontam(
        [
            "emit-risk-bulletin",
            "--corpus",
            str(DATA),
            "--store",
            str(STORE),
            "--cutoff",
            CUTOFF,
            "--emitted-at",
            EMITTED_AT,
            "--out",
            str(out),
        ]
    )
    assert proc.returncode != 0


def test_emit_rejects_tampered_mutation_attest():
    """emit must reject a tampered mutation_attest digest."""
    reset_workspace()
    score_bulletin(DATA, WORK / "p2_entry.json")
    warrant = json.loads((STORE / "mutation_chain_receipt.json").read_text())
    warrant["mutation_attest"] = "0" * 64
    (STORE / "mutation_chain_receipt.json").write_text(json.dumps(warrant, indent=2) + "\n")
    out = WORK / "fail2_entry.json"
    proc = run_wincontam(
        [
            "emit-risk-bulletin",
            "--corpus",
            str(DATA),
            "--store",
            str(STORE),
            "--cutoff",
            CUTOFF,
            "--emitted-at",
            EMITTED_AT,
            "--out",
            str(out),
        ]
    )
    assert proc.returncode != 0


def test_score_rejects_live_stamp_divergence():
    """score must fail when live corpus_stamp diverges from the hold snapshot."""
    reset_workspace()
    proc = run_wincontam(["absorb-context-hold", "--corpus", str(DATA), "--store", str(STORE)])
    assert proc.returncode == 0
    mutated = WORK / "stale_entry"
    shutil.copytree(DATA, mutated)
    sessions = json.loads((mutated / "conversation_sessions.json").read_text())
    sessions["sessions"].append(
        {"session_id": "sess_gamma", "opened_at": "2024-05-01T00:00:00Z", "domain": "other"}
    )
    (mutated / "conversation_sessions.json").write_text(json.dumps(sessions, indent=2) + "\n")
    out = WORK / "stale_out_entry.json"
    proc = run_wincontam(
        [
            "score-contam-window",
            "--corpus",
            str(mutated),
            "--store",
            str(STORE),
            "--cutoff",
            CUTOFF,
            "--emitted-at",
            EMITTED_AT,
            "--out",
            str(out),
        ]
    )
    assert proc.returncode != 0


def test_identical_clocks_yield_byte_stable_bulletin():
    """Matching corpus and clocks must yield byte-identical bulletins."""
    reset_workspace()
    a = WORK / "a_entry.json"
    score_bulletin(DATA, a)
    bytes_a = a.read_bytes()
    reset_workspace()
    b = WORK / "b_entry.json"
    score_bulletin(DATA, b)
    assert bytes_a == b.read_bytes()


def test_hidden_corpora_match_private_oracle():
    """Every hidden contamination corpus must match the private oracle bulletin."""
    for folder in HIDDEN:
        reset_workspace()
        cutoff = CUTOFF
        if folder == "hidden_future_turn_excluded":
            cutoff = "2024-03-01T00:00:00Z"
        corpus = mirror_corpus(folder, WORK / f"hid_{folder}")
        report = score_bulletin(corpus, WORK / f"hid_{folder}.json", cutoff=cutoff)
        assert report == reference_bulletin(corpus, cutoff, EMITTED_AT)


def test_hidden_trap_fixture_root_present():
    """Hidden corpora resolve under /opt/verifier-fixtures when mounted."""
    from wincontam_harness import fixture_root
    root = fixture_root()
    assert root.is_dir()
    assert str(root) in {"/opt/verifier-fixtures", str(Path(__file__).resolve().parent / "fixtures")} or root.name == "fixtures"


def test_hidden_trap_uses_verifier_fixtures_catalog():
    """TB3_CONTEXT_HOLD_PROBE catalog must list instruction and turnover traps."""
    from wincontam_harness import HIDDEN
    assert "hidden_instruction_conflict" in HIDDEN
    assert "hidden_stale_retrieval" in HIDDEN
