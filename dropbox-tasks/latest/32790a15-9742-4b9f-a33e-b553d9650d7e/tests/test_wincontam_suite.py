"""wincontam eval suite — contamination inference features and severity metrics."""

from __future__ import annotations

import json
import shutil

import pytest

from wincontam_harness import (
    BIN,
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


@pytest.fixture(autouse=True)
def _clean_store():
    reset_workspace()
    yield


def test_cli_binary_path_ready():
    """Release binary wincontam must exist after offline rebuild."""
    assert BIN.is_file()


def test_default_data_report_parity():
    """Bundled corpus bulletin must match the independent reference oracle."""
    report = score_bulletin(DATA, WORK / "bundled.json")
    assert report == reference_bulletin(DATA, CUTOFF, EMITTED_AT)


def test_row_key_ordering_contract():
    """contam_rows must sort by session_id, turn_id, contam_id."""
    report = score_bulletin(DATA, WORK / "sort.json")
    keys = [(r["session_id"], r["turn_id"], r["contam_id"]) for r in report["contam_rows"]]
    assert keys == sorted(keys)


def test_token_octet_sorted_contract():
    """Each contam row must carry exactly eight lexicographically sorted evidence tokens."""
    report = score_bulletin(DATA, WORK / "ev.json")
    for row in report["contam_rows"]:
        assert len(row["evidence"]) == 8
        assert row["evidence"] == sorted(row["evidence"])


def test_digest_object_singleton_key():
    """attestation must be exactly {attest_digest}."""
    report = score_bulletin(DATA, WORK / "att.json")
    assert set(report["attestation"].keys()) == {"attest_digest"}


def test_scoring_writes_three_store_artifacts():
    """score-contam-window must seal freeze, mutation receipt, and session risk ledger."""
    score_bulletin(DATA, WORK / "seals.json")
    assert (STORE / "context_hold_freeze.json").is_file()
    assert (STORE / "mutation_chain_receipt.json").is_file()
    assert (STORE / "session_risk_ledger.json").is_file()


def test_emit_preserves_sealed_rows_after_wipe():
    """emit-risk-bulletin must emit sealed freeze rows even after live corpus mutation."""
    report = score_bulletin(DATA, WORK / "before.json")
    sealed = json.loads((STORE / "context_hold_freeze.json").read_text())
    mutated = WORK / "mut_corpus"
    shutil.copytree(DATA, mutated)
    failures = json.loads((mutated / "model_output_failures.json").read_text())
    failures["failures"] = []
    (mutated / "model_output_failures.json").write_text(json.dumps(failures, indent=2) + "\n")
    out = WORK / "packaged.json"
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


def test_emit_fails_when_freeze_absent():
    """emit without context_hold_freeze.json must fail."""
    score_bulletin(DATA, WORK / "p1.json")
    (STORE / "context_hold_freeze.json").unlink()
    out = WORK / "fail.json"
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
    assert not out.exists()


def test_emit_fails_when_receipt_digest_altered():
    """Tampered mutation_attest must be rejected by emit."""
    score_bulletin(DATA, WORK / "p2.json")
    warrant = json.loads((STORE / "mutation_chain_receipt.json").read_text())
    warrant["mutation_attest"] = "0" * 64
    (STORE / "mutation_chain_receipt.json").write_text(json.dumps(warrant, indent=2) + "\n")
    out = WORK / "fail2.json"
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


def test_scoring_fails_on_stamp_drift():
    """score must reject when live corpus_stamp diverges from snapshot."""
    proc = run_wincontam(["absorb-context-hold", "--corpus", str(DATA), "--store", str(STORE)])
    assert proc.returncode == 0
    mutated = WORK / "stale"
    shutil.copytree(DATA, mutated)
    sessions = json.loads((mutated / "conversation_sessions.json").read_text())
    sessions["sessions"].append(
        {"session_id": "sess_gamma", "opened_at": "2024-05-01T00:00:00Z", "domain": "other"}
    )
    (mutated / "conversation_sessions.json").write_text(json.dumps(sessions, indent=2) + "\n")
    out = WORK / "stale_out.json"
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


def test_repeat_run_output_bytes_stable():
    """Identical clocks and corpus must yield byte-identical bulletins."""
    a = WORK / "a.json"
    score_bulletin(DATA, a)
    bytes_a = a.read_bytes()
    reset_workspace()
    b = WORK / "b.json"
    score_bulletin(DATA, b)
    assert bytes_a == b.read_bytes()


def test_suite_contam_summary_parity():
    """Bundled eval metric bulletin schema must match the reference contamination model."""
    report = score_bulletin(DATA, WORK / "metric.json")
    expected = reference_bulletin(DATA, CUTOFF, EMITTED_AT)
    assert report["contam_summary"] == expected["contam_summary"]
    assert report["coverage"] == expected["coverage"]


def test_suite_primary_cause_lane_parity():
    """Inference feature batch fields on contam rows must match the reference model."""
    report = score_bulletin(DATA, WORK / "feat.json")
    expected = reference_bulletin(DATA, CUTOFF, EMITTED_AT)
    assert [r["attribution_primary"] for r in report["contam_rows"]] == [
        r["attribution_primary"] for r in expected["contam_rows"]
    ]


@pytest.mark.parametrize("folder", HIDDEN)
def test_private_fixture_report_parity(folder: str):
    """Each hidden contamination corpus under /opt/verifier-fixtures must match the independent reference bulletin."""
    cutoff = CUTOFF
    if folder == "hidden_future_turn_excluded":
        cutoff = "2024-03-01T00:00:00Z"
    corpus = mirror_corpus(folder, WORK / folder)
    report = score_bulletin(corpus, WORK / f"{folder}.json", cutoff=cutoff)
    assert report == reference_bulletin(corpus, cutoff, EMITTED_AT)


@pytest.mark.parametrize(
    "folder,cause",
    [
        ("hidden_instruction_conflict", "instruction_conflict"),
        ("hidden_stale_retrieval", "stale_retrieval"),
        ("hidden_stale_post_failure", "stale_retrieval"),
        ("hidden_tool_artifact_bleed", "tool_artifact_bleed"),
        ("hidden_repeated_fact", "repeated_fact_injection"),
        ("hidden_residual_contam", "residual_contam"),
        ("hidden_instruction_over_stale", "instruction_conflict"),
    ],
)
def test_cause_matrix_primary_lock(folder: str, cause: str):
    """Named fixtures must lock the expected attribution_primary cause."""
    corpus = mirror_corpus(folder, WORK / f"cause_{folder}")
    report = score_bulletin(corpus, WORK / f"cause_{folder}.json")
    assert report["contam_rows"][0]["attribution_primary"] == cause


def test_stale_post_failure_pre_cutoff_hash_change():
    """Hash change after failure but before cutoff must still attribute stale_retrieval."""
    corpus = mirror_corpus("hidden_stale_post_failure", WORK / "spf")
    report = score_bulletin(corpus, WORK / "spf.json")
    assert len(report["contam_rows"]) == 1
    assert report["contam_rows"][0]["attribution_primary"] == "stale_retrieval"


def test_stale_equal_timestamps_are_not_later():
    """Equal retrieved_at with different hashes must not attribute stale_retrieval."""
    corpus = mirror_corpus("hidden_stale_equal_timestamps", WORK / "seq")
    report = score_bulletin(corpus, WORK / "seq.json")
    assert len(report["contam_rows"]) == 1
    assert report["contam_rows"][0]["attribution_primary"] != "stale_retrieval"
    assert report["contam_rows"][0]["attribution_primary"] == "residual_contam"


def test_emit_rejects_ledger_stamp_mismatch():
    """emit must reject when session_risk_ledger corpus_stamp diverges from freeze."""
    score_bulletin(DATA, WORK / "ledger_stamp.json")
    ledger = json.loads((STORE / "session_risk_ledger.json").read_text())
    ledger["corpus_stamp"] = "0" * 64
    (STORE / "session_risk_ledger.json").write_text(json.dumps(ledger, indent=2) + "\n")
    out = WORK / "ledger_stamp_fail.json"
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
    assert not out.exists()


def test_future_window_yields_no_rows():
    """Future turns beyond cutoff must not emit contam rows."""
    corpus = mirror_corpus("hidden_future_turn_excluded", WORK / "fe")
    report = score_bulletin(corpus, WORK / "fe.json", cutoff="2024-03-01T00:00:00Z")
    assert report["contam_rows"] == []


def test_clean_session_yields_no_rows():
    """Corpus without failures must emit zero contam rows."""
    corpus = mirror_corpus("hidden_stable_no_contam", WORK / "st")
    report = score_bulletin(corpus, WORK / "st.json")
    assert report["contam_rows"] == []


def test_boundary_cutoff_retains_failure():
    """Failure turn completed_at equal to cutoff must be included."""
    corpus = mirror_corpus("hidden_sim_clock_inclusive", WORK / "inc")
    report = score_bulletin(corpus, WORK / "inc.json")
    assert len(report["contam_rows"]) == 1
    assert report["contam_rows"][0]["turn_id"] == "t2"


def test_failure_key_last_wins_survivor():
    """Duplicate failure_id last-wins must keep the later turn_id survivor."""
    corpus = mirror_corpus("hidden_last_wins_failure", WORK / "lw")
    report = score_bulletin(corpus, WORK / "lw.json")
    assert len(report["contam_rows"]) == 1
    assert report["contam_rows"][0]["turn_id"] == "t_a4"


def test_severity_rounding_two_places():
    """severity_score must respect score_precision from policy."""
    corpus = mirror_corpus("hidden_score_precision", WORK / "sp")
    report = score_bulletin(corpus, WORK / "sp.json")
    assert report["session_scorecard"][0]["severity_score"] == 0.67
