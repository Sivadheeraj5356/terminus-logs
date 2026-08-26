"""Milestone 4 reference — multi-tamper localization for a presented audit log.

An external auditor is handed a *presented* transparency log (a list of entry
dicts) plus a trusted-key registry, and must localize, per entry, the exact
sorted set of integrity failures. Reasons are independent, accumulating
predicates — a single tamper routinely trips several at once — so each is
computed on its own and all that fire are collected.
"""

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

GENESIS = "0" * 64

REASONS = (
    "bad_signature",
    "broken_chain",
    "entry_hash_mismatch",
    "index_inconsistent",
    "replay",
    "untrusted_key",
)


def key_id(raw_pub: bytes) -> str:
    """Fingerprint of a raw 32-byte Ed25519 public key: sha256(raw)[:16] hex."""
    return hashlib.sha256(raw_pub).hexdigest()[:16]


def recompute_entry_hash(index, prev_hash, manifest_hash, signature) -> str:
    payload = json.dumps(
        {"index": index, "manifest_hash": manifest_hash,
         "prev_hash": prev_hash, "signature": signature},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_pub(b64):
    try:
        raw = base64.b64decode(b64)
        return Ed25519PublicKey.from_public_bytes(raw), raw
    except Exception:
        return None, None


def localize_entry(entry, position, prev_claimed_entry_hash, seen, trusted_key_ids) -> list:
    reasons = set()

    idx = entry.get("index")
    prev_hash = entry.get("prev_hash")
    manifest_hash = entry.get("manifest_hash")
    signature = entry.get("signature")
    claimed_eh = entry.get("entry_hash")
    pub_b64 = entry.get("public_key")

    # index must equal the entry's position in the presented log
    if idx != position:
        reasons.add("index_inconsistent")

    # hash chain: entry 0 links to genesis, others to the previous CLAIMED entry_hash
    expected_prev = GENESIS if position == 0 else prev_claimed_entry_hash
    if prev_hash != expected_prev:
        reasons.add("broken_chain")

    # entry_hash must recompute from the four committed fields
    if recompute_entry_hash(idx, prev_hash, manifest_hash, signature) != claimed_eh:
        reasons.add("entry_hash_mismatch")

    # trust + signature
    pub, raw = _load_pub(pub_b64)
    if pub is None or key_id(raw) not in trusted_key_ids:
        reasons.add("untrusted_key")
    else:
        # trusted key present: the signature must verify over the manifest hash
        try:
            pub.verify(base64.b64decode(signature), str(manifest_hash).encode("ascii"))
        except (InvalidSignature, Exception):  # noqa: BLE001
            reasons.add("bad_signature")

    # replay: this (manifest_hash, signature) already appeared earlier
    if (manifest_hash, signature) in seen:
        reasons.add("replay")

    return sorted(reasons)


def localize_log(entries: list, trusted_key_ids) -> list:
    """Return, per presented entry in order, {index, reasons (sorted), trusted}."""
    trusted_key_ids = set(trusted_key_ids)
    out = []
    seen = set()
    prev_claimed = GENESIS
    for pos, entry in enumerate(entries):
        reasons = localize_entry(entry, pos, prev_claimed, seen, trusted_key_ids)
        out.append({"index": entry.get("index"), "reasons": reasons,
                    "trusted": reasons == []})
        seen.add((entry.get("manifest_hash"), entry.get("signature")))
        prev_claimed = entry.get("entry_hash")
    return out


def audit_log(presented: dict) -> dict:
    """Top-level: {entries, trusted_key_ids} -> {rows, n_trusted, n_bad, per_reason}."""
    rows = localize_log(presented.get("entries", []), presented.get("trusted_key_ids", []))
    per_reason = {r: 0 for r in REASONS}
    n_trusted = 0
    for row in rows:
        for r in row["reasons"]:
            if r in per_reason:
                per_reason[r] += 1
        if row["trusted"]:
            n_trusted += 1
    return {"rows": rows, "n_trusted": n_trusted,
            "n_bad": len(rows) - n_trusted, "per_reason": per_reason}
