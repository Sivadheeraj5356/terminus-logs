#!/usr/bin/env python3
"""Generate deterministic audit bundles for artifact-quorum-release-gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "bundles"

CUSTODIAN_SPECS = {
    "alpha": 3,
    "beta": 2,
    "gamma": 2,
    "delta": 1,
    "epsilon": 1,
}


def _private_key(name: str) -> Ed25519PrivateKey:
    seed = hashlib.sha256(f"artifact-quorum::{name}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def _public_hex(name: str) -> str:
    key = _private_key(name)
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return raw.hex()


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


def sign_query(
    bundle_id: str,
    query_id: str,
    artifact_sha256_hex: str,
    scope: str,
    release_epoch: int,
    min_weight: int,
    custodian_ids: list[str],
) -> list[dict[str, str]]:
    msg = signing_bytes(
        bundle_id, query_id, artifact_sha256_hex, scope, release_epoch, min_weight
    )
    out: list[dict[str, str]] = []
    for cid in custodian_ids:
        sig = _private_key(cid).sign(msg).hex()
        out.append({"custodian_id": cid, "signature_hex": sig})
    return out


def custodian_map() -> dict[str, dict[str, object]]:
    return {
        cid: {"public_key_hex": _public_hex(cid), "weight": weight}
        for cid, weight in CUSTODIAN_SPECS.items()
    }


def write_bundle(bundle_id: str, payload: dict) -> None:
    payload = dict(payload)
    payload["bundle_id"] = bundle_id
    payload.setdefault("custodians", custodian_map())
    dest = OUT / bundle_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "bundle.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def artifact_hex(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def main() -> None:
    base_at = 1_700_000_000
    art = artifact_hex("release-candidate-v9")

    write_bundle(
        "basic_quorum_ok",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "promote",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 3600,
                    "min_weight": 5,
                    "signatures": sign_query(
                        "basic_quorum_ok",
                        "promote",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 3600,
                        5,
                        ["alpha", "beta"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "exact_weight_match",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "edge",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/stage/",
                    "release_epoch": base_at - 60,
                    "min_weight": 5,
                    "signatures": sign_query(
                        "exact_weight_match",
                        "edge",
                        art,
                        "custody|release|/artifacts/stage/",
                        base_at - 60,
                        5,
                        ["alpha", "gamma"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "insufficient_weight",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "short",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 120,
                    "min_weight": 5,
                    "signatures": sign_query(
                        "insufficient_weight",
                        "short",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 120,
                        5,
                        ["beta", "delta"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "single_heavy_custodian",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "solo",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/hotfix/",
                    "release_epoch": base_at - 10,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "single_heavy_custodian",
                        "solo",
                        art,
                        "custody|release|/artifacts/hotfix/",
                        base_at - 10,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "revoked_custodian",
        {
            "revoked_custodians": ["beta"],
            "queries": [
                {
                    "query_id": "blocked",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 30,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "revoked_custodian",
                        "blocked",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 30,
                        3,
                        ["beta", "alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "unknown_custodian",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "ghost",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 30,
                    "min_weight": 1,
                    "signatures": [
                        {"custodian_id": "zeta", "signature_hex": "00" * 64},
                    ],
                }
            ],
        },
    )

    write_bundle(
        "duplicate_signer",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "twice",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 30,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "duplicate_signer",
                        "twice",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 30,
                        3,
                        ["alpha"],
                    )
                    + sign_query(
                        "duplicate_signer",
                        "twice",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 30,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    bad_sig = sign_query(
        "bad_signature",
        "tampered",
        art,
        "custody|release|/artifacts/prod/",
        base_at - 30,
        3,
        ["alpha"],
    )
    bad_sig[0]["signature_hex"] = "ab" * 64
    write_bundle(
        "bad_signature",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "tampered",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 30,
                    "min_weight": 3,
                    "signatures": bad_sig,
                }
            ],
        },
    )

    write_bundle(
        "scope_malformed",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "badscope",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release",
                    "release_epoch": base_at - 30,
                    "min_weight": 1,
                    "signatures": sign_query(
                        "scope_malformed",
                        "badscope",
                        art,
                        "custody|release",
                        base_at - 30,
                        1,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "epoch_future",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "ahead",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at + 301,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "epoch_future",
                        "ahead",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at + 301,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "epoch_stale",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "old",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 86401,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "epoch_stale",
                        "old",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 86401,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "boundary_future_ok",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "limit",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at + 300,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "boundary_future_ok",
                        "limit",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at + 300,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "boundary_stale_ok",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "fresh",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 86400,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "boundary_stale_ok",
                        "fresh",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 86400,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "empty_signatures",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "none",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 10,
                    "min_weight": 3,
                    "signatures": [],
                }
            ],
        },
    )

    write_bundle(
        "unicode_scope_ok",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "uni",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/über/",
                    "release_epoch": base_at - 10,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "unicode_scope_ok",
                        "uni",
                        art,
                        "custody|release|/artifacts/über/",
                        base_at - 10,
                        3,
                        ["alpha"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "multi_query_mixed",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "a",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 10,
                    "min_weight": 3,
                    "signatures": sign_query(
                        "multi_query_mixed",
                        "a",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 10,
                        3,
                        ["alpha"],
                    ),
                },
                {
                    "query_id": "b",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 10,
                    "min_weight": 5,
                    "signatures": sign_query(
                        "multi_query_mixed",
                        "b",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 10,
                        5,
                        ["alpha", "beta"],
                    ),
                },
                {
                    "query_id": "c",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at - 10,
                    "min_weight": 5,
                    "signatures": sign_query(
                        "multi_query_mixed",
                        "c",
                        art,
                        "custody|release|/artifacts/prod/",
                        base_at - 10,
                        5,
                        ["delta"],
                    ),
                },
            ],
        },
    )

    write_bundle(
        "stress_many_sigs",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "fleet",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/fleet/",
                    "release_epoch": base_at - 5,
                    "min_weight": 6,
                    "signatures": sign_query(
                        "stress_many_sigs",
                        "fleet",
                        art,
                        "custody|release|/artifacts/fleet/",
                        base_at - 5,
                        6,
                        ["alpha", "beta", "gamma", "delta"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "many_custodians_ok",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "wide",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/wide/",
                    "release_epoch": base_at - 5,
                    "min_weight": 4,
                    "signatures": sign_query(
                        "many_custodians_ok",
                        "wide",
                        art,
                        "custody|release|/artifacts/wide/",
                        base_at - 5,
                        4,
                        ["beta", "gamma", "delta", "epsilon"],
                    ),
                }
            ],
        },
    )

    write_bundle(
        "future_boundary_deny",
        {
            "revoked_custodians": [],
            "queries": [
                {
                    "query_id": "over",
                    "eval_at": base_at,
                    "artifact_sha256_hex": art,
                    "scope": "custody|release|/artifacts/prod/",
                    "release_epoch": base_at + 301,
                    "min_weight": 1,
                    "signatures": [],
                }
            ],
        },
    )

    print(f"wrote bundles under {OUT}")


if __name__ == "__main__":
    main()
