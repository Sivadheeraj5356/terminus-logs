"""Reverse-engineered CT-log entry canonicalization + signed-input recovery.

This module is the deliverable for milestone 6. It is placed at exactly
``/app/transparency/entrycanon.py`` and imported as ``entrycanon`` with
``/app/transparency`` on ``sys.path``.

The canonicalization rule is NOT documented anywhere; it was recovered from the
worked example pairs shipped under ``/app/transparency/entrylog/examples`` (each
entry alongside the exact ``canonical`` bytes the log hashes, the ``leaf_hash``,
and the ``signed_input`` the Ed25519 log key signs). The rule is a CONJUNCTION of
several interacting axes recovered by cross-correlating the examples:

Signed scope (a fixed projection, partly CONDITIONAL on other fields):
  * always signed, in this curated order (NOT alphabetical):
        log_id, leaf_type, index, subject, issued_at, payload
  * ``issuer_id`` is signed -- emitted right after ``leaf_type`` -- ONLY when
    ``leaf_type == "precert_entry"``; for ``x509_entry`` it is excluded even when
    present.
  * every ``x_*`` extension key is out of scope, EXCEPT ``x_origin``, which is
    signed last under the bare key name ``origin``.
  * ``received_at`` and the ``audit`` block are out of scope.

Canonical bytes are a domain-prefixed, record-separated line (NOT JSON):

    b"ct-log-entry:v4\\n"
    + RS.join( key "=" value  for each in-scope field, in scope order )
    + b"\\n"

where RS is 0x1e and each value is sub-encoded:

  * ``index``     -> 16-digit zero-padded decimal
  * ``issued_at`` -> integer epoch MILLISECONDS (RFC3339 parsed; a fractional
                     part is kept to ms, a whole second still scales by 1000)
  * ``subject``   -> DNS names lower-cased, each non-ASCII label IDNA/punycode
                     encoded, de-duplicated, then sorted by REVERSED labels (TLD
                     first) with a "*" wildcard sorting AFTER its concrete
                     siblings and a depth tie-break (deeper name first when one
                     is a sub-domain of the other), joined by ","
  * ``payload``   -> hex of sha256(b"ct-payload:v4\\n" + leaf_type + 0x1f +
                     payload) -- a leaf_type-keyed, domain-separated payload hash
  * ``log_id`` / ``leaf_type`` / ``issuer_id`` / ``origin`` -> raw utf-8

The leaf hash is ``sha256(canonical_bytes)``; the value the log's Ed25519 key
signs is ``b"ct-log-leaf:v4\\n" + leaf_hash`` (a SECOND domain-separated hash,
not the canonical bytes directly).
"""

from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ENTRY_DOMAIN = b"ct-log-entry:v4\n"
LEAF_DOMAIN = b"ct-log-leaf:v4\n"
PAYLOAD_DOMAIN = b"ct-payload:v4\n"
_RS = b"\x1e"
_US = b"\x1f"

# Always-present curated (non-alphabetical) signed-scope field order.
BASE_SCOPE_FIELDS = ("log_id", "leaf_type", "index", "subject", "issued_at",
                     "payload")


class CanonError(ValueError):
    """Raised when an entry cannot be canonicalized."""


# --------------------------------------------------------------------------- #
# subject canonicalization
# --------------------------------------------------------------------------- #


def _puny_label(label: str) -> str:
    try:
        label.encode("ascii")
        return label
    except UnicodeEncodeError:
        return label.encode("idna").decode("ascii")


def _puny_name(name: str) -> str:
    return ".".join(_puny_label(lab) for lab in name.lower().split("."))


def _reversed_labels(puny_name: str):
    labels = puny_name.split(".")
    return ["￿" if lab == "*" else lab for lab in reversed(labels)]


def _name_cmp(a: str, b: str) -> int:
    ra, rb = _reversed_labels(a), _reversed_labels(b)
    for la, lb in zip(ra, rb):
        if la != lb:
            return -1 if la < lb else 1
    if len(ra) == len(rb):
        return 0
    # one reversed-label list is a prefix of the other -> deeper name first
    return -1 if len(ra) > len(rb) else 1


def canonical_subject(subject) -> str:
    """IDNA-normalized, de-duplicated, reversed-label-sorted DNS subject."""
    if subject is None:
        return ""
    if isinstance(subject, str):
        names = [subject]
    elif isinstance(subject, list):
        if not all(isinstance(s, str) for s in subject):
            raise CanonError("subject entries must be strings")
        names = list(subject)
    else:
        raise CanonError("subject must be a string or list of strings")
    uniq = list(dict.fromkeys(_puny_name(n) for n in names))
    uniq.sort(key=functools.cmp_to_key(_name_cmp))
    return ",".join(uniq)


# --------------------------------------------------------------------------- #
# timestamp -> epoch milliseconds
# --------------------------------------------------------------------------- #


def epoch_millis(ts) -> int:
    """RFC3339 / epoch-seconds -> integer epoch MILLISECONDS."""
    if isinstance(ts, bool):
        raise CanonError("bad timestamp")
    if isinstance(ts, int):
        return ts * 1000
    if not isinstance(ts, str):
        raise CanonError("timestamp must be a string or int")
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError as exc:
        raise CanonError(f"cannot parse timestamp {ts!r}") from exc
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(round(d.timestamp() * 1000))


def _encode_index(idx) -> str:
    if isinstance(idx, bool):
        raise CanonError("index must not be a bool")
    if isinstance(idx, int):
        value = idx
    elif isinstance(idx, str):
        try:
            value = int(idx)
        except ValueError as exc:
            raise CanonError(f"cannot parse index {idx!r}") from exc
    else:
        raise CanonError("index must be an int or numeric string")
    if value < 0:
        raise CanonError("index must be non-negative")
    return format(value, "016d")


def _payload_hash_hex(entry: dict) -> str:
    payload = entry.get("payload")
    if not isinstance(payload, str):
        raise CanonError("payload must be a string")
    leaf_type = entry.get("leaf_type")
    if not isinstance(leaf_type, str):
        raise CanonError("leaf_type must be a string")
    return hashlib.sha256(
        PAYLOAD_DOMAIN + leaf_type.encode("utf-8") + _US
        + payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# projection (conditional) + canonical bytes
# --------------------------------------------------------------------------- #


def _scope_pairs(entry: dict):
    """Ordered (emit_key, source_key) pairs actually signed for this entry."""
    pairs = []
    for k in BASE_SCOPE_FIELDS:
        pairs.append((k, k))
        if k == "leaf_type" and entry.get("leaf_type") == "precert_entry":
            pairs.append(("issuer_id", "issuer_id"))
    if "x_origin" in entry:
        pairs.append(("origin", "x_origin"))
    return pairs


def _value_bytes(emit_key: str, src_key: str, entry: dict) -> bytes:
    if emit_key in ("log_id", "leaf_type", "issuer_id", "origin"):
        v = entry.get(src_key)
        if not isinstance(v, str):
            raise CanonError(f"{emit_key} must be a string")
        return v.encode("utf-8")
    if emit_key == "index":
        return _encode_index(entry.get("index")).encode("ascii")
    if emit_key == "subject":
        return canonical_subject(entry.get("subject")).encode("utf-8")
    if emit_key == "issued_at":
        return str(epoch_millis(entry.get("issued_at"))).encode("ascii")
    if emit_key == "payload":
        return _payload_hash_hex(entry).encode("ascii")
    raise CanonError(f"unknown field {emit_key!r}")


def signed_scope(entry: dict) -> dict:
    """Project an entry to exactly the signed fields (normalized)."""
    if not isinstance(entry, dict):
        raise CanonError("entry must be a dict")
    out = {}
    for emit_key, src_key in _scope_pairs(entry):
        if emit_key == "index":
            out["index"] = _encode_index(entry.get("index"))
        elif emit_key == "subject":
            out["subject"] = canonical_subject(entry.get("subject"))
        elif emit_key == "issued_at":
            out["issued_at"] = epoch_millis(entry.get("issued_at"))
        elif emit_key == "payload":
            out["payload"] = _payload_hash_hex(entry)
        else:
            out[emit_key] = entry.get(src_key)
    return out


def canonicalize_entry(entry: dict) -> bytes:
    """Return the exact canonical bytes the CT log hashes for ``entry``."""
    if not isinstance(entry, dict):
        raise CanonError("entry must be a dict")
    parts = [emit_key.encode("ascii") + b"=" + _value_bytes(emit_key, src_key, entry)
             for emit_key, src_key in _scope_pairs(entry)]
    return ENTRY_DOMAIN + _RS.join(parts) + b"\n"


def leaf_hash(entry: dict) -> bytes:
    """sha256 of the canonical entry bytes (the Merkle leaf hash)."""
    return hashlib.sha256(canonicalize_entry(entry)).digest()


def signed_input(entry: dict) -> bytes:
    """The exact bytes the log's Ed25519 key signs for ``entry``."""
    return LEAF_DOMAIN + leaf_hash(entry)


def verify_entry_signature(entry: dict, signature_b64: str,
                           public_key_b64: str) -> bool:
    """True iff ``signature_b64`` is a valid Ed25519 signature over
    ``signed_input(entry)`` under the raw base64 public key. Never raises."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64))
        pub.verify(base64.b64decode(signature_b64), signed_input(entry))
        return True
    except (InvalidSignature, CanonError, ValueError, TypeError):
        return False


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="entrycanon")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("canonicalize")
    c.add_argument("--entry", required=True)
    c.add_argument("--out", required=True)
    s = sub.add_parser("signed-input")
    s.add_argument("--entry", required=True)
    s.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    with open(args.entry, encoding="utf-8") as fh:
        entry = json.load(fh)
    data = canonicalize_entry(entry) if args.cmd == "canonicalize" \
        else signed_input(entry)
    with open(args.out, "wb") as fh:
        fh.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
