"""Behavioral checks for the fixed Cipherwave security audit packet."""

from __future__ import annotations

import json

import reference


def test_packet_bytes_match_independent_cryptographic_derivation(expected, packet):
    """Every deliverable must match the independently authenticated incident world."""

    mismatched = [
        name
        for name in sorted(set(packet) | set(expected["bytes"]))
        if packet.get(name) != expected["bytes"].get(name)
    ]
    assert not mismatched, f"mismatched incident artifact bytes: {mismatched}"


def test_custody_authenticates_and_qualifies_both_rotation_keys(expected, packet):
    """Custody must bind sources and qualify current then candidate without key leakage."""

    custody = json.loads(packet["custody.json"])
    assert custody == expected["custody"]
    assert custody["ready"] is True
    assert [row["role"] for row in custody["keys"]] == ["current", "candidate"]
    assert all(row["qualified"] and row["reason"] == "qualified" for row in custody["keys"])
    assert all(len(row["keyHandle"]) == 64 for row in custody["keys"])
    assert all("wrappedKey" not in row and "nonce" not in row for row in custody["keys"])


def test_evidence_validates_complete_hls_fragment_universe(expected, packet):
    """Evidence must reconcile every rendition and surface through signed AES-CBC proofs."""

    evidence = json.loads(packet["evidence.json"])
    assert evidence == expected["evidence"]
    assert len(evidence["rows"]) == 6
    assert [(row["rendition"], row["surface"]) for row in evidence["rows"]] == [
        ("audio", "published"),
        ("audio", "staged"),
        ("hd", "published"),
        ("hd", "staged"),
        ("sd", "published"),
        ("sd", "staged"),
    ]
    absent = [row for row in evidence["rows"] if not row["present"]]
    assert [(row["rendition"], row["surface"], row["reason"]) for row in absent] == [
        ("audio", "staged", "absent")
    ]
    present = [row for row in evidence["rows"] if row["present"]]
    assert all(row["valid"] and row["reason"] == "valid" for row in present)
    assert all(row["fragments"] for row in present)
    assert all(fragment["valid"] for row in present for fragment in row["fragments"])


def test_authorization_replays_signed_heads_and_checkpoint_quorum(expected, packet):
    """The proof must authenticate the full ledger and expose final amendment heads."""

    proof = json.loads(packet["authorization-proof.json"])
    assert proof == expected["authorization"]
    assert proof["checkpoint"]["treeSize"] == 28
    assert proof["checkpoint"]["validSignerIds"] == [
        f"guardian-{index:03d}" for index in range(96)
    ]
    reasons = [row["reason"] for row in proof["heads"]]
    assert reasons.count("operative") == 18
    assert reasons.count("revoked") == 3
    assert reasons.count("stale_profile") == 1
    assert reasons.count("stale_generation") == 1
    assert any(row["revision"] == 2 and row["reason"] == "operative" for row in proof["heads"])


def test_authorization_selects_exact_resilient_greedy_trap_witness(expected, packet):
    """The selected witness must be the global risk/count/ID optimum after any org loss."""

    proof = json.loads(packet["authorization-proof.json"])
    assert proof["required"] is True and proof["ready"] is True
    assert proof["selectedApprovalIds"] == [
        "approval-full-alpha",
        "approval-full-beta",
        "approval-full-gamma",
    ]
    assert proof["selectedOrganizations"] == ["alpha", "beta", "gamma"]
    assert proof["selectedCount"] == 3
    assert proof["totalRisk"] == 6
    assert len(proof["coverage"]) == 3
    for row in proof["coverage"]:
        assert type(row["selectedApprovals"]) is int, (
            "coverage.selectedApprovals must be an integer count, not an ID array"
        )
        assert row["selectedApprovals"] == 3
        assert [item["organization"] for item in row["organizationLoads"]] == [
            "alpha",
            "beta",
            "delta",
            "epsilon",
            "gamma",
            "zeta",
        ]
        assert min(item["survivingApprovals"] for item in row["survivorsAfterLoss"]) == 2


def test_certificate_applies_global_rotation_precedence_and_actions(expected, packet):
    """Certificate decision, rendition states, and actions must follow the global matrix."""

    certificate = json.loads(packet["rotation-certificate.json"])
    assert certificate == expected["certificate"]
    assert certificate["decision"] in {
        "quarantine",
        "finish_commit",
        "commit",
        "rollback_pending",
        "hold_current",
    }
    assert [row["rendition"] for row in certificate["renditions"]] == ["audio", "hd", "sd"]
    assert [row["rendition"] for row in certificate["actions"]] == ["audio", "hd", "sd"]
    assert len(certificate["seal"]) == 64
    assert set(certificate["keyConfirmations"]) == {"current", "candidate"}


def test_certificate_core_binds_authorization_and_keeps_row_shapes_distinct(expected, packet):
    """Core, proof, and plan must bind exact bytes without conflating rendition shapes."""

    certificate = json.loads(packet["rotation-certificate.json"])
    proof_bytes = packet["authorization-proof.json"]
    assert certificate["sources"]["authorizationSha256"] == reference.sha256_hex(
        proof_bytes
    )
    core = {
        "schema": "cipherwave.rotation-core.v1",
        "profileId": certificate["profileId"],
        "auditUnix": certificate["auditUnix"],
        "sources": certificate["sources"],
        "decision": certificate["decision"],
        "currentKey": certificate["currentKey"],
        "candidateKey": certificate["candidateKey"],
        "renditions": certificate["renditions"],
        "actions": certificate["actions"],
    }
    assert expected["plan"]["certificateCoreSha256"] == reference.sha256_hex(
        reference.canonical_json(core)
    )
    assert all(set(row) == {"rendition", "state"} for row in core["renditions"])
    assert expected["plan"]["renditions"] == ["audio", "hd", "sd"]
    assert all(
        set(row) == {"rendition", "action"}
        for row in expected["authorization"]["requestedActions"]
    )


def test_plan_is_bound_to_certificate_and_candidate_authorization(expected, packet):
    """The plan must carry the exact certificate, plan-body, key, IV, and action bindings."""

    assert packet["ffmpeg-plan.toml"] == expected["planToml"]
    certificate = expected["certificate"]
    plan = expected["plan"]
    plan_body = {key: value for key, value in plan.items() if key != "certificateSha256"}
    assert certificate["planBodySha256"] == reference.sha256_hex(
        reference.canonical_json(plan_body)
    )
    assert plan["certificateSha256"]
    assert bool(plan["enabled"]) == (certificate["decision"] in {"commit", "finish_commit"})
    assert plan["actions"] == certificate["actions"]
