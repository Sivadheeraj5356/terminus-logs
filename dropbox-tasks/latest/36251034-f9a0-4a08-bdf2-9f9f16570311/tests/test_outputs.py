"""Verifier for /app/output/release_audit.json via independent reference evaluator."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ref_quorum import reference_report

APP = Path("/app")
BUNDLES = APP / "data" / "bundles"
OUTPUT = APP / "output" / "release_audit.json"
BIN = APP / "bin" / "quorumgate"

BUNDLE_IDS = [
    "basic_quorum_ok",
    "exact_weight_match",
    "insufficient_weight",
    "single_heavy_custodian",
    "revoked_custodian",
    "unknown_custodian",
    "duplicate_signer",
    "bad_signature",
    "scope_malformed",
    "epoch_future",
    "epoch_stale",
    "boundary_future_ok",
    "boundary_stale_ok",
    "empty_signatures",
    "unicode_scope_ok",
    "multi_query_mixed",
    "stress_many_sigs",
    "many_custodians_ok",
    "future_boundary_deny",
]

DECISION_CASES = [
    ("basic_quorum_ok", "promote", "allow", "quorum_ok"),
    ("exact_weight_match", "edge", "allow", "quorum_ok"),
    ("insufficient_weight", "short", "deny", "insufficient_quorum"),
    ("single_heavy_custodian", "solo", "allow", "quorum_ok"),
    ("revoked_custodian", "blocked", "deny", "revoked_custodian"),
    ("unknown_custodian", "ghost", "deny", "unknown_custodian"),
    ("duplicate_signer", "twice", "deny", "duplicate_custodian"),
    ("bad_signature", "tampered", "deny", "signature_invalid"),
    ("scope_malformed", "badscope", "deny", "scope_malformed"),
    ("epoch_future", "ahead", "deny", "epoch_future"),
    ("epoch_stale", "old", "deny", "epoch_stale"),
    ("boundary_future_ok", "limit", "allow", "quorum_ok"),
    ("boundary_stale_ok", "fresh", "allow", "quorum_ok"),
    ("empty_signatures", "none", "deny", "insufficient_quorum"),
    ("unicode_scope_ok", "uni", "allow", "quorum_ok"),
    ("multi_query_mixed", "a", "allow", "quorum_ok"),
    ("multi_query_mixed", "b", "allow", "quorum_ok"),
    ("multi_query_mixed", "c", "deny", "insufficient_quorum"),
    ("stress_many_sigs", "fleet", "allow", "quorum_ok"),
    ("many_custodians_ok", "wide", "allow", "quorum_ok"),
    ("future_boundary_deny", "over", "deny", "epoch_future"),
]

WEIGHT_CASES = [
    ("basic_quorum_ok", "promote", 5),
    ("exact_weight_match", "edge", 5),
    ("insufficient_weight", "short", 3),
    ("single_heavy_custodian", "solo", 3),
    ("empty_signatures", "none", 0),
    ("stress_many_sigs", "fleet", 8),
    ("many_custodians_ok", "wide", 6),
]

VERIFIED_CASES = [
    ("basic_quorum_ok", "promote", 2),
    ("bad_signature", "tampered", 0),
    ("stress_many_sigs", "fleet", 4),
    ("duplicate_signer", "twice", 1),
    ("multi_query_mixed", "b", 2),
]

UNIQUE_CASES = [
    ("duplicate_signer", "twice", 1),
    ("stress_many_sigs", "fleet", 4),
    ("empty_signatures", "none", 0),
    ("unknown_custodian", "ghost", 1),
]

STATS_CASES = [
    ("multi_query_mixed", 3, 2, 1, 0, 1, 0),
    ("stress_many_sigs", 1, 1, 0, 0, 0, 0),
    ("revoked_custodian", 1, 0, 1, 0, 0, 1),
    ("bad_signature", 1, 0, 1, 1, 0, 0),
    ("insufficient_weight", 1, 0, 1, 0, 1, 0),
]

_REPORT_CACHE: dict[str, dict] = {}


def _run_bundle(bundle_id: str, *, use_cache: bool = True) -> dict:
    if use_cache:
        cached = _REPORT_CACHE.get(bundle_id)
        if cached is not None:
            return cached
    bundle_path = BUNDLES / bundle_id / "bundle.json"
    if OUTPUT.exists():
        OUTPUT.unlink()
    proc = subprocess.run(
        [str(BIN), "--bundle", str(bundle_path), "--output", str(OUTPUT)],
        cwd=APP,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUTPUT.exists(), "release_audit.json missing"
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if use_cache:
        _REPORT_CACHE[bundle_id] = report
    return report


def _result_map(report: dict) -> dict[str, dict]:
    return {row["query_id"]: row for row in report["results"]}


@pytest.mark.parametrize("bundle_id", BUNDLE_IDS)
def test_report_matches_reference(bundle_id: str) -> None:
    """Full report must match the independent reference evaluator."""
    got = _run_bundle(bundle_id)
    want = reference_report(bundle_id)
    assert got == want


@pytest.mark.parametrize(
    ("bundle_id", "query_id", "decision", "reason"),
    DECISION_CASES,
    ids=[f"{b}:{q}" for b, q, _, _ in DECISION_CASES],
)
def test_query_decision_and_reason(
    bundle_id: str, query_id: str, decision: str, reason: str
) -> None:
    """Each scenario must emit the contract decision and terminal reason."""
    row = _result_map(_run_bundle(bundle_id))[query_id]
    assert row["decision"] == decision
    assert row["reason"] == reason


@pytest.mark.parametrize(
    ("bundle_id", "query_id", "quorum_weight"),
    WEIGHT_CASES,
    ids=[f"{b}:{q}" for b, q, _ in WEIGHT_CASES],
)
def test_quorum_weight(bundle_id: str, query_id: str, quorum_weight: int) -> None:
    """Verified custodian weights must sum into quorum_weight."""
    row = _result_map(_run_bundle(bundle_id))[query_id]
    assert row["quorum_weight"] == quorum_weight


@pytest.mark.parametrize(
    ("bundle_id", "query_id", "signatures_verified"),
    VERIFIED_CASES,
    ids=[f"{b}:{q}" for b, q, _ in VERIFIED_CASES],
)
def test_signatures_verified(
    bundle_id: str, query_id: str, signatures_verified: int
) -> None:
    """Ed25519 verification count must follow the ordered scan rules."""
    row = _result_map(_run_bundle(bundle_id))[query_id]
    assert row["signatures_verified"] == signatures_verified


@pytest.mark.parametrize(
    ("bundle_id", "query_id", "unique_custodians"),
    UNIQUE_CASES,
    ids=[f"{b}:{q}" for b, q, _ in UNIQUE_CASES],
)
def test_unique_custodians(
    bundle_id: str, query_id: str, unique_custodians: int
) -> None:
    """unique_custodians counts distinct ids in the submission list."""
    row = _result_map(_run_bundle(bundle_id))[query_id]
    assert row["unique_custodians"] == unique_custodians


@pytest.mark.parametrize(
    ("bundle_id", "total", "allowed", "denied", "sig_fail", "quorum_fail", "revoked"),
    STATS_CASES,
    ids=[b for b, *_ in STATS_CASES],
)
def test_stats_counters(
    bundle_id: str,
    total: int,
    allowed: int,
    denied: int,
    sig_fail: int,
    quorum_fail: int,
    revoked: int,
) -> None:
    """Aggregate stats must follow the reason-code tally rules."""
    stats = _run_bundle(bundle_id)["stats"]
    assert stats["queries_total"] == total
    assert stats["allowed"] == allowed
    assert stats["denied"] == denied
    assert stats["signature_failures"] == sig_fail
    assert stats["quorum_failures"] == quorum_fail
    assert stats["revoked_hits"] == revoked


@pytest.mark.parametrize("bundle_id", BUNDLE_IDS)
def test_results_sorted_by_query_id(bundle_id: str) -> None:
    """results must be sorted ascending by query_id before write."""
    results = _run_bundle(bundle_id)["results"]
    ids = [row["query_id"] for row in results]
    assert ids == sorted(ids)


@pytest.mark.parametrize("bundle_id", BUNDLE_IDS)
def test_eval_profile_constant(bundle_id: str) -> None:
    """eval_profile must remain artifact-quorum-v1."""
    report = _run_bundle(bundle_id)
    assert report["eval_profile"] == "artifact-quorum-v1"


@pytest.mark.parametrize("bundle_id", BUNDLE_IDS)
def test_state_digest_is_64_hex(bundle_id: str) -> None:
    """state_digest must be lowercase hex SHA-256."""
    digest = _run_bundle(bundle_id)["state_digest"]
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)


@pytest.mark.parametrize("bundle_id", BUNDLE_IDS[:6])
def test_deterministic_rerun(bundle_id: str) -> None:
    """Repeated runs on the same bundle must be byte-identical."""
    first = _run_bundle(bundle_id, use_cache=False)
    second = _run_bundle(bundle_id, use_cache=False)
    assert first == second
