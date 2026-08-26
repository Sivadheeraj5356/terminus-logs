"""Reference evaluator for artifact-quorum-release-gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

APP = Path("/app")
BUNDLES = APP / "data" / "bundles"
EVAL_PROFILE = "artifact-quorum-v1"
MAX_RELEASE_AGE_SEC = 86400
MAX_FUTURE_SKEW_SEC = 300


def signing_bytes(
    bundle_id: str,
    query_id: str,
    artifact_sha256_hex: str,
    scope: str,
    release_epoch: int,
    min_weight: int,
) -> bytes:
    lines = [
        "artifact-quorum-v1",
        bundle_id,
        query_id,
        artifact_sha256_hex,
        scope,
        str(release_epoch),
        str(min_weight),
    ]
    return "\n".join(lines).encode("utf-8")


def scope_well_formed(scope: str) -> bool:
    parts = scope.split("|")
    if len(parts) != 3:
        return False
    return all(part != "" for part in parts)


def epoch_future(eval_at: int, release_epoch: int) -> bool:
    return release_epoch > eval_at + MAX_FUTURE_SKEW_SEC


def epoch_stale(eval_at: int, release_epoch: int) -> bool:
    return eval_at - release_epoch > MAX_RELEASE_AGE_SEC


def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    if len(signature_hex) != 128:
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pk.verify(bytes.fromhex(signature_hex), message)
    except (InvalidSignature, ValueError):
        return False
    return True


def evaluate_query(bundle: dict, query: dict) -> dict:
    unique_custodians = len({s["custodian_id"] for s in query["signatures"]})
    bundle_id = bundle["bundle_id"]
    custodians = bundle["custodians"]
    revoked = set(bundle.get("revoked_custodians", []))

    if not scope_well_formed(query["scope"]):
        return {
            "query_id": query["query_id"],
            "decision": "deny",
            "reason": "scope_malformed",
            "quorum_weight": 0,
            "signatures_verified": 0,
            "unique_custodians": unique_custodians,
        }

    if epoch_future(query["eval_at"], query["release_epoch"]):
        return {
            "query_id": query["query_id"],
            "decision": "deny",
            "reason": "epoch_future",
            "quorum_weight": 0,
            "signatures_verified": 0,
            "unique_custodians": unique_custodians,
        }

    if epoch_stale(query["eval_at"], query["release_epoch"]):
        return {
            "query_id": query["query_id"],
            "decision": "deny",
            "reason": "epoch_stale",
            "quorum_weight": 0,
            "signatures_verified": 0,
            "unique_custodians": unique_custodians,
        }

    msg = signing_bytes(
        bundle_id,
        query["query_id"],
        query["artifact_sha256_hex"],
        query["scope"],
        query["release_epoch"],
        query["min_weight"],
    )

    seen: set[str] = set()
    verified_weight = 0
    verified_count = 0

    for entry in query["signatures"]:
        cid = entry["custodian_id"]
        if cid in seen:
            return {
                "query_id": query["query_id"],
                "decision": "deny",
                "reason": "duplicate_custodian",
                "quorum_weight": verified_weight,
                "signatures_verified": verified_count,
                "unique_custodians": unique_custodians,
            }
        seen.add(cid)

        if cid not in custodians:
            return {
                "query_id": query["query_id"],
                "decision": "deny",
                "reason": "unknown_custodian",
                "quorum_weight": verified_weight,
                "signatures_verified": verified_count,
                "unique_custodians": unique_custodians,
            }

        if cid in revoked:
            return {
                "query_id": query["query_id"],
                "decision": "deny",
                "reason": "revoked_custodian",
                "quorum_weight": verified_weight,
                "signatures_verified": verified_count,
                "unique_custodians": unique_custodians,
            }

        ok = verify_signature(
            custodians[cid]["public_key_hex"], msg, entry["signature_hex"]
        )
        if not ok:
            return {
                "query_id": query["query_id"],
                "decision": "deny",
                "reason": "signature_invalid",
                "quorum_weight": verified_weight,
                "signatures_verified": verified_count,
                "unique_custodians": unique_custodians,
            }

        verified_count += 1
        verified_weight += int(custodians[cid]["weight"])

    if verified_weight < query["min_weight"]:
        return {
            "query_id": query["query_id"],
            "decision": "deny",
            "reason": "insufficient_quorum",
            "quorum_weight": verified_weight,
            "signatures_verified": verified_count,
            "unique_custodians": unique_custodians,
        }

    return {
        "query_id": query["query_id"],
        "decision": "allow",
        "reason": "quorum_ok",
        "quorum_weight": verified_weight,
        "signatures_verified": verified_count,
        "unique_custodians": unique_custodians,
    }


def state_digest(results: list[dict], stats: dict) -> str:
    rows = sorted(results, key=lambda r: r["query_id"])
    parts: list[str] = []
    for row in rows:
        parts.append(
            "\t".join(
                [
                    row["query_id"],
                    row["decision"],
                    row["reason"],
                    str(row["quorum_weight"]),
                    str(row["signatures_verified"]),
                    str(row["unique_custodians"]),
                ]
            )
        )
    parts.append(
        "\t".join(
            [
                "stats",
                str(stats["queries_total"]),
                str(stats["allowed"]),
                str(stats["denied"]),
                str(stats["signature_failures"]),
                str(stats["quorum_failures"]),
                str(stats["revoked_hits"]),
            ]
        )
    )
    body = "\n".join(parts)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_report(bundle_id: str) -> dict:
    bundle = json.loads((BUNDLES / bundle_id / "bundle.json").read_text(encoding="utf-8"))
    results = [evaluate_query(bundle, q) for q in bundle["queries"]]
    results.sort(key=lambda r: r["query_id"])

    stats = {
        "queries_total": len(results),
        "allowed": sum(1 for r in results if r["decision"] == "allow"),
        "denied": sum(1 for r in results if r["decision"] == "deny"),
        "signature_failures": sum(1 for r in results if r["reason"] == "signature_invalid"),
        "quorum_failures": sum(1 for r in results if r["reason"] == "insufficient_quorum"),
        "revoked_hits": sum(1 for r in results if r["reason"] == "revoked_custodian"),
    }

    return {
        "bundle_id": bundle_id,
        "eval_profile": EVAL_PROFILE,
        "results": results,
        "stats": stats,
        "state_digest": state_digest(results, stats),
    }
