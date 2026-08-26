"""Authenticated endorsement and complete-frontier behavioral checks."""

from __future__ import annotations

import json
from collections import Counter

import reference
from helpers import FIXTURE_DIR


def _frontier_rows(data: bytes) -> list[dict]:
    """Decode canonical JSONL without accepting blank rows."""

    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
    lines = data.splitlines()
    assert lines and all(lines)
    return [json.loads(line) for line in lines]


def test_checkpoint_endorsements_apply_complete_fail_closed_precedence(expected, packet):
    """Every valid and decoy endorsement must receive the documented first verdict."""

    proof = json.loads(packet["authorization-proof.json"])
    assert proof["checkpointEndorsements"] == expected["authorization"][
        "checkpointEndorsements"
    ]
    counts = Counter(row["reason"] for row in proof["checkpointEndorsements"])
    assert counts == {
        "valid": 96,
        "duplicate_guardian": 1,
        "guardian_inactive": 1,
        "guardian_out_of_window": 1,
        "guardian_compromised": 1,
        "bad_signature": 1,
        "unknown_guardian": 1,
    }
    assert len(proof["checkpoint"]["validSignerIds"]) == 96
    assert len(proof["checkpoint"]["validOrganizations"]) == 32


def test_checkpoint_frontier_materializes_every_reachable_coordinate(expected, packet):
    """The JSONL artifact must contain the complete large coalesced state space."""

    data = packet["checkpoint-frontier.jsonl"]
    assert data == expected["checkpointFrontierBytes"]
    rows = _frontier_rows(data)
    summary = expected["authorization"]["checkpointFrontier"]
    assert len(rows) == summary["stateCount"]
    assert len(rows) > 20_000
    coordinates = [
        (int(row["coverageMask"], 16), row["cappedWeight"]) for row in rows
    ]
    assert coordinates == sorted(coordinates)
    assert len(coordinates) == len(set(coordinates))


def test_frontier_rows_and_state_digest_use_exact_preimages(expected, packet):
    """Every representative and the ordered state commitment must hash canonically."""

    rows = _frontier_rows(packet["checkpoint-frontier.jsonl"])
    for row in rows:
        assert list(row) == [
            "cappedWeight",
            "coverageMask",
            "guardianIds",
            "rowDigest",
            "selectedCount",
            "totalLag",
            "totalWeight",
        ]
        base = {key: value for key, value in row.items() if key != "rowDigest"}
        assert row["rowDigest"] == reference.sha256_hex(reference.canonical_json(base))
        assert row["guardianIds"] == sorted(
            row["guardianIds"], key=lambda value: value.encode("utf-8")
        )
        assert row["selectedCount"] == len(row["guardianIds"])
    state_digest = reference.sha256_hex(
        b"".join(bytes.fromhex(row["rowDigest"]) for row in rows)
    )
    assert state_digest == expected["authorization"]["checkpointFrontier"][
        "stateDigest"
    ]


def test_selected_checkpoint_witness_is_operator_distinct_global_optimum(expected, packet):
    """The required coordinate must retain the exact count/lag/weight/ID optimum."""

    proof = json.loads(packet["authorization-proof.json"])
    witness = proof["checkpointFrontier"]["selectedWitness"]
    assert witness == expected["authorization"]["checkpointFrontier"][
        "selectedWitness"
    ]
    assert witness["coverageMask"] == "0fff"
    assert witness["cappedWeight"] == 24
    assert witness["guardianIds"] == [
        "guardian-000",
        "guardian-003",
        "guardian-006",
    ]
    trust = json.loads((FIXTURE_DIR / "guardian-trust.json").read_bytes())
    operator_by_id = {
        row["guardianId"]: row["checkpointOperator"] for row in trust["guardians"]
    }
    operators = [operator_by_id[value] for value in witness["guardianIds"]]
    assert len(operators) == len(set(operators))


def test_frontier_exact_bytes_are_load_bearing_through_the_final_plan(expected, packet):
    """Frontier bytes must alter proof, certificate core, certificate, and plan bindings."""

    proof_bytes = packet["authorization-proof.json"]
    frontier_bytes = packet["checkpoint-frontier.jsonl"]
    proof = json.loads(proof_bytes)
    certificate = json.loads(packet["rotation-certificate.json"])
    assert proof["sources"]["checkpointFrontierSha256"] == reference.sha256_hex(
        frontier_bytes
    )
    assert proof["checkpointFrontier"]["frontierSha256"] == reference.sha256_hex(
        frontier_bytes
    )
    assert certificate["sources"]["authorizationSha256"] == reference.sha256_hex(
        proof_bytes
    )
    assert packet["ffmpeg-plan.toml"] == expected["planToml"]

