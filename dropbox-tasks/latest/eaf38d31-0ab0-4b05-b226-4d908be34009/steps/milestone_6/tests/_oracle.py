"""Independent reference for the undocumented CT-log entry canonicalization (v4).

Test-private. Re-implements the TRUE entry-canonicalization + signed-scope rule a
DIFFERENT way from the agent's solution (manual byte assembly, hand-rolled
comparator, explicit epoch/punycode arithmetic) so that agreement with the
agent's output is real cross-check evidence, not shared code. It never imports
the agent module. It also holds the deterministic Ed25519 signing seed (NOT
shipped to /app) so it can sign its own held-out corpus.

The rule (NEVER stated to the agent; recovered ONLY from the worked example
pairs). It is intentionally a CONJUNCTION of several interacting, non-obvious
axes -- no single example reveals the whole thing:

  signed scope (field projection -- some of it CONDITIONAL on other fields)
    Always in scope, in this FIXED curated order (not alphabetical):
        log_id, leaf_type, index, subject, issued_at, payload
    CONDITIONAL field:
        issuer_id  -- signed (emitted right AFTER leaf_type) *only when*
                      leaf_type == "precert_entry"; for "x509_entry" it is
                      EXCLUDED even when present in the entry.
    Reserved-prefix exclusion WITH one carve-out:
        every top-level key beginning with "x_" is OUT of scope ...
        EXCEPT "x_origin", which IS signed -- emitted LAST, under the bare key
        name "origin" (the "x_" prefix dropped). All other x_* are ignored.
    Other out-of-scope (mutating them leaves the bytes unchanged):
        the whole "audit" block, "received_at" (server receive time).

  canonical bytes
    domain prefix  b"ct-log-entry:v4\n"
    then the in-scope fields in the order described above, each emitted as
        key "=" value     joined by the RS byte 0x1e, terminated by 0x0a
    value sub-encoding by field:
        log_id    : raw string bytes (utf-8)
        leaf_type : raw string bytes (utf-8)
        issuer_id : raw string bytes (utf-8)   [only present for precerts]
        index     : 16-digit zero-padded decimal
        subject   : the canonicalized DNS names (see below), comma-joined
        issued_at : integer epoch MILLISECONDS (RFC3339 parsed; a fractional
                    part is KEPT to millisecond precision, an absent fractional
                    part still scales by 1000)
        payload   : hex of sha256(b"ct-payload:v4\n" + leaf_type_utf8 + 0x1f +
                    payload_utf8) -- a DOMAIN-SEPARATED, leaf_type-KEYED payload
                    hash (NOT a bare sha256 of the payload)
        origin    : raw string bytes (utf-8) of x_origin   [only if present]

  subject canonicalization (reversed-label order + 2 tie-breaks + idna + dedup)
    * each name is lower-cased, then every NON-ASCII label is IDNA/punycode
      encoded to its "xn--" a-label form (ASCII labels pass through unchanged);
    * de-duplicate on the resulting punycoded lower name;
    * sort key = the labels REVERSED (TLD first); a "*" wildcard label maps to
      the HIGH sentinel "￿" so a wildcard sorts AFTER its concrete
      siblings under the same parent (NOT before);
    * tie-break (when one reversed-label key is a prefix of another): the name
      with MORE labels (deeper) sorts FIRST;
    * join with ",".

  leaf hash       sha256(canonical_bytes)
  signed_input    b"ct-log-leaf:v4\n" + leaf_hash   (Ed25519 signs THIS, a
                  SECOND domain-separated value, not the canonical bytes)
"""
from __future__ import annotations

import base64 as _b64
import hashlib as _hl
from datetime import datetime as _dt
from datetime import timezone as _tz

from cryptography.exceptions import InvalidSignature as _InvalidSig
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey as _Priv,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey as _Pub,
)

_DOMAIN = b"ct-log-entry:v4\n"
_LEAF_DOMAIN = b"ct-log-leaf:v4\n"
_PAYLOAD_DOMAIN = b"ct-payload:v4\n"
_RS = b"\x1e"
_US = b"\x1f"

# Always-present curated (NON-alphabetical) field order for the signed scope.
_BASE_ORDER = ("log_id", "leaf_type", "index", "subject", "issued_at", "payload")

# Deterministic log signing seed (kept ONLY here, never under /app).
_LOG_SEED = b"ct-log-entry-oracle-seed-v4!!!xx"[:32]


class _Bad(Exception):
    pass


def _log_priv() -> _Priv:
    return _Priv.from_private_bytes(_LOG_SEED)


def _log_pub_b64() -> str:
    from cryptography.hazmat.primitives import serialization as _ser
    raw = _log_priv().public_key().public_bytes(
        _ser.Encoding.Raw, _ser.PublicFormat.Raw)
    return _b64.b64encode(raw).decode()


# --------------------------------------------------------------------------- #
# subject canonicalization: idna + reversed-label order, wildcard sorts LAST,
# depth tie-break, dedup
# --------------------------------------------------------------------------- #


def _puny_label(label: str) -> str:
    """ASCII label -> unchanged; non-ASCII label -> its punycode a-label."""
    try:
        label.encode("ascii")
        return label
    except UnicodeEncodeError:
        # builtin idna codec, label at a time (the "*" wildcard is ASCII so it
        # never reaches here).
        return label.encode("idna").decode("ascii")


def _puny_name(name: str) -> str:
    return ".".join(_puny_label(lab) for lab in name.lower().split("."))


def _rev_labels(puny_name: str):
    """Labels reversed (TLD first); a "*" wildcard label maps to the HIGH
    sentinel so a wildcard sorts AFTER concrete siblings under the same parent."""
    labels = puny_name.split(".")
    return ["￿" if lab == "*" else lab for lab in reversed(labels)]


def _cmp_names(a: str, b: str) -> int:
    """Reversed-label comparator with the prefix (depth) tie-break: compare
    reversed labels position-by-position; if one name's reversed-label list is a
    strict PREFIX of the other's (same parent zone, one is a sub-domain of the
    other), the DEEPER name (more labels) sorts FIRST."""
    ra, rb = _rev_labels(a), _rev_labels(b)
    for la, lb in zip(ra, rb):
        if la != lb:
            return -1 if la < lb else 1
    if len(ra) == len(rb):
        return 0
    # one is a prefix of the other -> deeper (longer) sorts first
    return -1 if len(ra) > len(rb) else 1


def _canon_subject(subject) -> str:
    import functools
    if subject is None:
        return ""
    if isinstance(subject, str):
        names = [subject]
    elif isinstance(subject, list):
        for s in subject:
            if not isinstance(s, str):
                raise _Bad("subject name not str")
        names = list(subject)
    else:
        raise _Bad("subject type")
    # punycode + lower-case, then de-duplicate on the resulting name.
    seen = {}
    for n in names:
        seen[_puny_name(n)] = None
    uniq = list(seen.keys())
    uniq.sort(key=functools.cmp_to_key(_cmp_names))
    return ",".join(uniq)


# --------------------------------------------------------------------------- #
# timestamp -> integer epoch MILLISECONDS (fractional part KEPT to ms)
# --------------------------------------------------------------------------- #


def _epoch_millis(ts) -> int:
    if isinstance(ts, bool):
        raise _Bad("bool timestamp")
    if isinstance(ts, int):
        return ts * 1000
    if not isinstance(ts, str):
        raise _Bad("timestamp type")
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = _dt.fromisoformat(s)
    except ValueError as e:
        raise _Bad("timestamp parse") from e
    if d.tzinfo is None:
        d = d.replace(tzinfo=_tz.utc)
    # whole-millisecond epoch (round half-to-even at us boundary is irrelevant:
    # all evidence is at most ms precision). Keep the fractional ms.
    return int(round(d.timestamp() * 1000))


def _enc_index(idx) -> str:
    if isinstance(idx, bool):
        raise _Bad("bool index")
    if isinstance(idx, int):
        v = idx
    elif isinstance(idx, str):
        try:
            v = int(idx)
        except ValueError as e:
            raise _Bad("index parse") from e
    else:
        raise _Bad("index type")
    if v < 0:
        raise _Bad("negative index")
    return format(v, "016d")


def _payload_hash(entry: dict) -> str:
    p = entry.get("payload")
    if not isinstance(p, str):
        raise _Bad("payload")
    lt = entry.get("leaf_type")
    if not isinstance(lt, str):
        raise _Bad("leaf_type")
    return _hl.sha256(
        _PAYLOAD_DOMAIN + lt.encode("utf-8") + _US + p.encode("utf-8")
    ).hexdigest()


def _scope_keys(entry: dict):
    """The ordered list of (emit_key, source_key) pairs actually signed for this
    entry (projection is partly CONDITIONAL on leaf_type / x_origin presence)."""
    lt = entry.get("leaf_type")
    keys = []
    for k in _BASE_ORDER:
        keys.append((k, k))
        if k == "leaf_type" and lt == "precert_entry":
            keys.append(("issuer_id", "issuer_id"))
    if "x_origin" in entry:
        keys.append(("origin", "x_origin"))
    return keys


def _field_value(emit_key: str, src_key: str, entry: dict) -> bytes:
    if emit_key in ("log_id", "leaf_type", "issuer_id", "origin"):
        v = entry.get(src_key)
        if not isinstance(v, str):
            raise _Bad(emit_key)
        return v.encode("utf-8")
    if emit_key == "index":
        return _enc_index(entry.get("index")).encode("ascii")
    if emit_key == "subject":
        return _canon_subject(entry.get("subject")).encode("utf-8")
    if emit_key == "issued_at":
        return str(_epoch_millis(entry.get("issued_at"))).encode("ascii")
    if emit_key == "payload":
        return _payload_hash(entry).encode("ascii")
    raise _Bad("unknown field")  # pragma: no cover


def _signed_scope(entry: dict) -> dict:
    """The projected, in-scope view (what is actually signed), normalized."""
    if not isinstance(entry, dict):
        raise _Bad("entry dict")
    out = {}
    for emit_key, src_key in _scope_keys(entry):
        if emit_key == "index":
            out["index"] = _enc_index(entry.get("index"))
        elif emit_key == "subject":
            out["subject"] = _canon_subject(entry.get("subject"))
        elif emit_key == "issued_at":
            out["issued_at"] = _epoch_millis(entry.get("issued_at"))
        elif emit_key == "payload":
            out["payload"] = _payload_hash(entry)
        else:
            out[emit_key] = entry.get(src_key)
    return out


def _canon(entry: dict) -> bytes:
    if not isinstance(entry, dict):
        raise _Bad("entry dict")
    parts = []
    for emit_key, src_key in _scope_keys(entry):
        parts.append(
            emit_key.encode("ascii") + b"=" + _field_value(emit_key, src_key, entry))
    return _DOMAIN + _RS.join(parts) + b"\n"


def _leaf_hash(entry: dict) -> bytes:
    return _hl.sha256(_canon(entry)).digest()


def _signed_input(entry: dict) -> bytes:
    return _LEAF_DOMAIN + _leaf_hash(entry)


def _sign(entry: dict) -> str:
    return _b64.b64encode(_log_priv().sign(_signed_input(entry))).decode()


def _verify(entry: dict, sig_b64: str, pub_b64: str | None = None) -> bool:
    try:
        raw = _b64.b64decode(pub_b64) if pub_b64 else _log_priv().public_key(
        ).public_bytes_raw()
        pub = _Pub.from_public_bytes(raw)
        pub.verify(_b64.b64decode(sig_b64), _signed_input(entry))
        return True
    except (_InvalidSig, _Bad, ValueError, TypeError):
        return False
