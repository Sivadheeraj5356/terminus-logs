"""Deterministic, verifier-owned vault generator for custody qualification.

The private seeds that select cases live in tests; this module deliberately
contains only the protocol encoder and never depends on candidate code.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(seed: int, label: str, length: int = 32) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(f"{seed}:{label}:{counter}".encode()).digest()
        counter += 1
    return out[:length]


def _key(seed: int, label: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_bytes(seed, label))


def _public(private: Ed25519PrivateKey) -> str:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def _signed(private: Ed25519PrivateKey, record: dict[str, Any]) -> dict[str, Any]:
    body = dict(record)
    body["signature"] = private.sign(canonical_json(record)).hex()
    return body


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value) + b"\n")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json(v) + b"\n" for v in values))


@dataclass
class Scenario:
    root: Path
    seed: int
    epoch: int
    expected_paths: list[str]
    plaintexts: dict[str, bytes]
    object_ids: dict[str, str]
    active_wraps: dict[str, str]


def build_vault(root: Path, seed: int, kind: str = "mixed") -> Scenario:
    """Create a read-only vault using the public on-disk schema.

    Kinds are intentionally composable enough for mutation-oriented tests:
    mixed, rollback, conflicting, historical, threshold, unauthorized,
    relocated, empty, and hidden.
    """
    if root.exists():
        shutil.rmtree(root)
    for name in ("objects", "envelopes", "authority", "rewrap", "shares", "keys", "state"):
        (root / name).mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    authority = _key(seed, "authority")
    audit = _key(seed, "audit")
    orgs = ["atlas", "boreal", "cinder"]
    aliases = {org: f"{org}-a-{rng.randrange(1000, 9999)}" for org in orgs}
    alias_keys = {alias: _key(seed, f"alias:{alias}") for alias in aliases.values()}
    epoch = 20 + seed % 7

    ledger: list[dict[str, Any]] = []
    for index, org in enumerate(orgs):
        record = {
            "kind": "authorize",
            "sequence": index + 1,
            "epoch": 1,
            "organization_id": org,
            "alias_id": aliases[org],
            "public_key": _public(alias_keys[aliases[org]]),
        }
        ledger.append(_signed(authority, record))
    # An alias activated after all normal object epochs exercises historical lookup.
    future_alias = f"future-{seed % 10000}"
    future_key = _key(seed, "future")
    ledger.append(_signed(authority, {
        "kind": "authorize", "sequence": 10, "epoch": epoch + 5,
        "organization_id": "future", "alias_id": future_alias, "public_key": _public(future_key),
    }))
    if kind == "historical":
        ledger.append(_signed(authority, {
            "kind": "revoke", "sequence": 11, "epoch": epoch + 2,
            "organization_id": "atlas", "alias_id": aliases["atlas"],
        }))
    _write_jsonl(root / "authority/ledger.jsonl", ledger)
    _write_json(root / "keys/appliance-audit-public.json", {"key_id": "audit-1", "public_key": _public(audit)})
    _write_json(
        root / "keys/appliance-audit-private.json",
        {"key_id": "audit-1", "private_key": _bytes(seed, "audit", 32).hex()},
    )

    manifest: dict[str, Any] = {
        "schema_version": 2,
        "policy_id": f"policy-{seed:08x}",
        "qualification_epoch": epoch,
        "authority_public_key": _public(authority),
        "threshold": 2,
        "objects": [],
    }
    plaintexts: dict[str, bytes] = {}
    object_ids: dict[str, str] = {}
    active_wraps: dict[str, str] = {}
    journal: list[dict[str, Any]] = []
    expected: list[str] = []
    if kind == "empty":
        _write_json(root / "manifest.json", manifest)
        _write_jsonl(root / "rewrap/journal.jsonl", [])
        return Scenario(root, seed, epoch, expected, plaintexts, object_ids, active_wraps)

    count = 3 if kind in ("mixed", "hidden", "threshold") else 1
    for index in range(count):
        object_id = sha256(_bytes(seed, f"object:{index}"))[:24]
        logical = f"tenant-{seed % 97}/document-{index}-{rng.randrange(100, 999)}.bin"
        version = 1 if index == 0 and kind in ("mixed", "hidden") else 2
        storage = f"blob-{sha256(_bytes(seed, f'storage:{index}'))[:18]}.bin"
        if kind == "relocated":
            storage = f"relocated-{storage}"
        plain = _bytes(seed, f"plaintext:{index}", 19 + index)
        data_key = _bytes(seed, f"data-key:{index}")
        nonce = _bytes(seed, f"nonce:{index}", 12)
        # v1 commits storage identity; v2 commits only canonical logical identity.
        aad = (
            b"ecrq/v1/" + storage.encode()
            if version == 1
            else b"ecrq/v2/" + logical.encode() + b"/" + object_id.encode()
        )
        ciphertext = AESGCM(data_key).encrypt(nonce, plain, aad)
        (root / "objects" / storage).write_bytes(ciphertext)
        parent = f"wrap-{object_id[:10]}-parent"
        child = f"wrap-{object_id[:10]}-child"
        for wrap_id, sequence, parent_id, state in (
            (parent, index * 10 + 1, None, "commit"),
            (child, index * 10 + 2, parent, "commit"),
        ):
            rec = {
                "kind": state, "sequence": sequence, "transaction_id": wrap_id,
                "parent_transaction_id": parent_id, "object_id": object_id,
                "epoch": epoch, "data_key_commitment": sha256(data_key),
                "plaintext_sha256": sha256(plain),
            }
            journal.append(_signed(authority, rec))
        if kind == "rollback":
            journal.append(_signed(authority, {
                "kind": "rollback", "sequence": index * 10 + 3, "transaction_id": child,
                "parent_transaction_id": parent, "object_id": object_id, "epoch": epoch,
            }))
            active_wraps[object_id] = parent
        else:
            active_wraps[object_id] = child
        if kind == "mixed":
            journal.append(_signed(authority, {
                "kind": "prepare", "sequence": index * 10 + 99, "transaction_id": f"new-{child}",
                "parent_transaction_id": child, "object_id": object_id, "epoch": epoch,
            }))
        if kind == "conflicting":
            bad = dict(journal[-1])
            bad["transaction_id"] = "conflicting-head"
            journal.append(bad)

        envelope = {
            "schema_version": version, "object_id": object_id, "logical_path": logical,
            "storage_name": storage, "custody_epoch": epoch, "nonce": nonce.hex(),
            "ciphertext_sha256": sha256(ciphertext), "data_key_commitment": sha256(data_key),
            "plaintext_sha256": sha256(plain), "active_wrap_id": active_wraps[object_id],
            "aad_identity": logical if version == 2 else storage,
        }
        _write_json(root / "envelopes" / f"{object_id}.json", envelope)
        manifest["objects"].append({"object_id": object_id, "logical_path": logical})
        plaintexts[logical] = plain
        object_ids[logical] = object_id
        expected.append(logical)

        shares: list[dict[str, Any]] = []
        selected_orgs = ["atlas", "boreal"]
        if kind == "threshold":
            selected_orgs = ["atlas", "atlas"]  # two aliases must not satisfy threshold
        for share_index, org in enumerate(selected_orgs):
            alias = aliases[org]
            signer = alias_keys[alias]
            rec = {
                "kind": "share", "share_id": f"{active_wraps[object_id]}-{share_index}",
                "wrap_id": active_wraps[object_id], "object_id": object_id, "epoch": epoch,
                "organization_id": org, "alias_id": alias, "share_value": (share_index + 1) * 17,
            }
            shares.append(_signed(signer, rec))
        if kind == "unauthorized":
            rec = {
                "kind": "share", "share_id": f"{active_wraps[object_id]}-future",
                "wrap_id": active_wraps[object_id], "object_id": object_id, "epoch": epoch,
                "organization_id": "future", "alias_id": future_alias, "share_value": 91,
            }
            shares[1] = _signed(future_key, rec)
        # The encrypted data key is verifier-private fixture information, not an output expectation.
        envelope["wrapped_data_key"] = base64.b64encode(data_key).decode()
        _write_json(root / "envelopes" / f"{object_id}.json", envelope)
        _write_jsonl(root / "shares" / f"{active_wraps[object_id]}.jsonl", shares)

    if kind == "historical":
        # A newer object cannot use an alias which was activated later.
        expected = expected[:1]
    if kind in ("threshold", "unauthorized", "conflicting"):
        expected = []
    _write_json(root / "manifest.json", manifest)
    _write_jsonl(root / "rewrap/journal.jsonl", journal)
    return Scenario(root, seed, epoch, sorted(expected), plaintexts, object_ids, active_wraps)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def tamper(path: Path, *, offset: int = 0) -> None:
    data = bytearray(path.read_bytes())
    if not data:
        raise ValueError(f"cannot tamper empty file: {path}")
    data[offset % len(data)] ^= 1
    path.write_bytes(data)
