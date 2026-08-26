"""Independent recovery-set reference model for ECRQ verifier fixtures."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _verify(record: dict[str, Any], public_hex: str) -> bool:
    signed = dict(record)
    signature = bytes.fromhex(signed.pop("signature"))
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(signature, canonical_json(signed))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _authority(vault: Path, epoch: int) -> dict[str, tuple[str, str]]:
    manifest = _json(vault / "manifest.json")
    aliases: dict[str, tuple[str, str]] = {}
    for record in sorted(_jsonl(vault / "authority/ledger.jsonl"), key=lambda r: r["sequence"]):
        if not _verify(record, manifest["authority_public_key"]):
            raise ValueError("invalid authority evidence")
        if record["epoch"] > epoch:
            continue
        alias = record["alias_id"]
        if record["kind"] == "authorize":
            aliases[alias] = (record["organization_id"], record["public_key"])
        elif record["kind"] == "revoke":
            aliases.pop(alias, None)
        else:
            raise ValueError("unknown authority record")
    return aliases


def _heads(vault: Path) -> dict[str, str]:
    manifest = _json(vault / "manifest.json")
    by_object: dict[str, list[dict[str, Any]]] = {}
    for record in _jsonl(vault / "rewrap/journal.jsonl"):
        if not _verify(record, manifest["authority_public_key"]):
            raise ValueError("invalid journal signature")
        by_object.setdefault(record["object_id"], []).append(record)
    out: dict[str, str] = {}
    for object_id, records in by_object.items():
        seen_sequences: set[int] = set()
        commits: dict[str, dict[str, Any]] = {}
        active = ""
        for rec in sorted(records, key=lambda r: r["sequence"]):
            seq = rec["sequence"]
            if seq in seen_sequences:
                raise ValueError("duplicate journal sequence")
            seen_sequences.add(seq)
            kind = rec["kind"]
            tx = rec["transaction_id"]
            parent = rec.get("parent_transaction_id")
            if kind == "prepare":
                continue
            if kind == "commit":
                if parent is not None and parent not in commits:
                    raise ValueError("unknown journal parent")
                if tx in commits:
                    raise ValueError("conflicting journal commit")
                commits[tx] = rec
                active = tx
            elif kind == "rollback":
                if tx != active or parent not in commits:
                    raise ValueError("invalid rollback")
                active = parent
            else:
                raise ValueError("unknown journal state")
        if active:
            out[object_id] = active
    return out


def _snapshot(vault: Path) -> str:
    members: list[dict[str, Any]] = []
    for rel in ("manifest.json", "authority/ledger.jsonl", "rewrap/journal.jsonl"):
        p = vault / rel
        members.append({"path": rel, "sha256": sha256(p.read_bytes())})
    for folder in ("objects", "envelopes", "shares"):
        for p in sorted((vault / folder).rglob("*")):
            if p.is_file():
                members.append({"path": p.relative_to(vault).as_posix(), "sha256": sha256(p.read_bytes())})
    members.sort(key=lambda item: item["path"])
    return sha256(canonical_json(members))


def _audit_envelope(vault: Path, statement: dict[str, Any]) -> dict[str, Any]:
    private_hex = _json(vault / "keys/appliance-audit-private.json")["private_key"]
    public_hex = _json(vault / "keys/appliance-audit-public.json")["public_key"]
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
    payload = canonical_json(statement)
    signature = private.sign(payload).hex()
    return {
        "payload": base64.b64encode(payload).decode(),
        "public_key": public_hex,
        "signatures": [{"keyid": "audit-1", "sig": signature}],
    }


def qualify_reference(vault: Path, *, epoch: int | None = None) -> dict[str, Any]:
    """Compute expected artifacts without executing application code."""
    manifest = _json(vault / "manifest.json")
    effective_epoch = manifest["qualification_epoch"] if epoch is None else epoch
    heads = _heads(vault)
    rows: list[dict[str, Any]] = []
    plaintexts: dict[str, bytes] = {}
    for item in manifest["objects"]:
        object_id = item["object_id"]
        env = _json(vault / "envelopes" / f"{object_id}.json")
        if env["custody_epoch"] > effective_epoch or object_id not in heads:
            continue
        if env["active_wrap_id"] != heads[object_id]:
            raise ValueError("envelope and committed head disagree")
        authorized = _authority(vault, env["custody_epoch"])
        shares = _jsonl(vault / "shares" / f"{heads[object_id]}.jsonl")
        organizations: set[str] = set()
        for share in shares:
            alias = share.get("alias_id")
            if alias not in authorized:
                continue
            org, public = authorized[alias]
            if share.get("organization_id") != org or not _verify(share, public):
                continue
            if share.get("wrap_id") == heads[object_id] and share.get("object_id") == object_id:
                organizations.add(org)
        if len(organizations) < manifest["threshold"]:
            continue
        ciphertext = (vault / "objects" / env["storage_name"]).read_bytes()
        if sha256(ciphertext) != env["ciphertext_sha256"]:
            raise ValueError("ciphertext commitment mismatch")
        aad = (
            b"ecrq/v1/" + env["storage_name"].encode()
            if env["schema_version"] == 1
            else b"ecrq/v2/" + env["logical_path"].encode() + b"/" + object_id.encode()
        )
        key = base64.b64decode(env["wrapped_data_key"])
        plain = AESGCM(key).decrypt(bytes.fromhex(env["nonce"]), ciphertext, aad)
        if sha256(plain) != env["plaintext_sha256"] or sha256(key) != env["data_key_commitment"]:
            raise ValueError("plaintext commitment mismatch")
        row = {
            "logical_path": env["logical_path"],
            "plaintext_size": len(plain),
            "plaintext_sha256": sha256(plain),
            "data_key_commitment": env["data_key_commitment"],
            "envelope_version": env["schema_version"],
            "custody_epoch": env["custody_epoch"],
            "active_rewrap_transaction_id": heads[object_id],
            "organizations": sorted(organizations),
            "recovery_status": "recovered",
        }
        rows.append(row)
        plaintexts[env["logical_path"]] = plain
    rows.sort(key=lambda r: r["logical_path"])
    inventory = b"".join(canonical_json(row) + b"\n" for row in rows)
    snapshot = _snapshot(vault)
    root = {
        "schema_version": 1,
        "policy_id": manifest["policy_id"],
        "evidence_snapshot_sha256": snapshot,
        "inventory_sha256": sha256(inventory),
        "object_digests": [row["plaintext_sha256"] for row in rows],
        "recovery_root": sha256(canonical_json({
            "policy_id": manifest["policy_id"], "snapshot": snapshot,
            "inventory": sha256(inventory), "objects": [row["plaintext_sha256"] for row in rows],
        })),
    }
    statement = {
        "recovery_root": root["recovery_root"],
        "evidence_snapshot_sha256": snapshot,
        "inventory_sha256": sha256(inventory),
    }
    audit = _audit_envelope(vault, statement)
    return {
        "rows": rows, "inventory_bytes": inventory, "recovery_root": root,
        "plaintexts": plaintexts, "heads": heads, "snapshot": snapshot,
        "audit": audit,
    }
