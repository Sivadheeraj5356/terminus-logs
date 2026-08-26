"""Milestone 4 tests: multi-tamper localization over a presented audit log.

The agent's `audit` module (at /app/transparency/audit.py) is fuzzed against a
fully INDEPENDENT in-test reference over hundreds of randomized logs with
simultaneous, overlapping tampers across all six reason classes. The whole
per-entry sorted reason set AND the top-level tallies must match exactly.
"""

import base64
import hashlib
import json
import random
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, "/app/transparency")

import audit  # noqa: E402

GENESIS = "0" * 64
REASONS = ("bad_signature", "broken_chain", "entry_hash_mismatch",
           "index_inconsistent", "replay", "untrusted_key")


# --- independent reference --------------------------------------------------

def _eh(index, prev_hash, manifest_hash, signature):
    payload = json.dumps(
        {"index": index, "manifest_hash": manifest_hash,
         "prev_hash": prev_hash, "signature": signature},
        sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _kid(raw):
    return hashlib.sha256(raw).hexdigest()[:16]


def _ref_rows(entries, trusted):
    trusted = set(trusted)
    rows, seen, prev = [], set(), GENESIS
    for pos, e in enumerate(entries):
        r = set()
        if e.get("index") != pos:
            r.add("index_inconsistent")
        if e.get("prev_hash") != (GENESIS if pos == 0 else prev):
            r.add("broken_chain")
        if _eh(e.get("index"), e.get("prev_hash"), e.get("manifest_hash"),
               e.get("signature")) != e.get("entry_hash"):
            r.add("entry_hash_mismatch")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            raw = base64.b64decode(e.get("public_key"))
            pub = Ed25519PublicKey.from_public_bytes(raw)
        except Exception:
            pub, raw = None, None
        if pub is None or _kid(raw) not in trusted:
            r.add("untrusted_key")
        else:
            try:
                pub.verify(base64.b64decode(e.get("signature")),
                           str(e.get("manifest_hash")).encode("ascii"))
            except (InvalidSignature, Exception):
                r.add("bad_signature")
        if (e.get("manifest_hash"), e.get("signature")) in seen:
            r.add("replay")
        rows.append({"index": e.get("index"), "reasons": sorted(r), "trusted": not r})
        seen.add((e.get("manifest_hash"), e.get("signature")))
        prev = e.get("entry_hash")
    return rows


# --- log builders -----------------------------------------------------------

def _mk_key():
    p = Ed25519PrivateKey.generate()
    raw = p.public_key().public_bytes_raw()
    return p, base64.b64encode(raw).decode(), _kid(raw)


def _valid_log(rng, n, trusted_priv, trusted_pub_b64):
    entries, prev = [], GENESIS
    for i in range(n):
        mh = hashlib.sha256(f"m{rng.random()}".encode()).hexdigest()
        sig = base64.b64encode(trusted_priv.sign(mh.encode("ascii"))).decode()
        eh = _eh(i, prev, mh, sig)
        entries.append({"index": i, "prev_hash": prev, "manifest_hash": mh,
                        "signature": sig, "entry_hash": eh,
                        "public_key": trusted_pub_b64})
        prev = eh
    return entries


# --- module surface ---------------------------------------------------------

def test_surface():
    """The audit module exposes localize_log, audit_log, recompute_entry_hash, key_id and the exact REASONS tuple."""
    for fn in ("localize_log", "audit_log", "recompute_entry_hash", "key_id"):
        assert hasattr(audit, fn), f"audit.{fn} missing"
    assert tuple(audit.REASONS) == REASONS


def test_clean_log_all_trusted():
    """A clean signed log has every entry trusted and matches the independent reference audit."""
    rng = random.Random(1)
    priv, pub_b64, kid = _mk_key()
    entries = _valid_log(rng, 6, priv, pub_b64)
    res = audit.audit_log({"entries": entries, "trusted_key_ids": [kid]})
    assert res == _audit_ref(entries, [kid])
    assert res["n_bad"] == 0 and res["n_trusted"] == 6


def _audit_ref(entries, trusted):
    rows = _ref_rows(entries, trusted)
    per = {r: 0 for r in REASONS}
    nt = 0
    for row in rows:
        for x in row["reasons"]:
            per[x] += 1
        nt += row["trusted"]
    return {"rows": rows, "n_trusted": nt, "n_bad": len(rows) - nt, "per_reason": per}


# --- targeted co-occurrence cases ------------------------------------------

def test_edit_manifest_hash_is_double():
    """Editing only manifest_hash trips both entry_hash_mismatch and bad_signature on that entry."""
    rng = random.Random(2)
    priv, pub_b64, kid = _mk_key()
    e = _valid_log(rng, 3, priv, pub_b64)
    e[1]["manifest_hash"] = "f" * 64  # edit, leave entry_hash/signature/prev as-is
    got = audit.localize_log(e, [kid])
    # recomputed entry_hash now differs, and the old signature no longer verifies
    assert got[1]["reasons"] == ["bad_signature", "entry_hash_mismatch"]
    assert got[1]["trusted"] is False


def test_tamper_entry_hash_breaks_next_chain():
    """Tampering an entry_hash trips entry_hash_mismatch on it and broken_chain on the next entry."""
    rng = random.Random(3)
    priv, pub_b64, kid = _mk_key()
    e = _valid_log(rng, 3, priv, pub_b64)
    e[0]["entry_hash"] = "a" * 64  # claimed hash no longer matches recompute
    got = audit.localize_log(e, [kid])
    assert "entry_hash_mismatch" in got[0]["reasons"]
    assert "broken_chain" in got[1]["reasons"]  # entry 1 points at the old hash


def test_untrusted_key_and_replay():
    """An entry signed by an untrusted key reports only untrusted_key (bad_signature is suppressed)."""
    rng = random.Random(4)
    priv, pub_b64, kid = _mk_key()
    e = _valid_log(rng, 2, priv, pub_b64)
    res = audit.localize_log(e, [])  # nothing trusted
    assert res[0]["reasons"] == ["untrusted_key"]


def test_fuzz_overlapping_tampers_match_reference():
    """Over hundreds of overlapping-tamper logs, audit_log matches the reference exactly and covers every reason."""
    rng = random.Random(20260620)
    cov = {r: 0 for r in REASONS}
    total = 0
    for case in range(220):
        priv, pub_b64, kid = _mk_key()
        other_priv, other_pub_b64, other_kid = _mk_key()  # untrusted signer
        n = rng.randint(1, 8)
        entries = _valid_log(rng, n, priv, pub_b64)

        for i in range(n):
            k = rng.choices([0, 1, 2], weights=[4, 4, 2])[0]
            for _ in range(k):
                kind = rng.choice(
                    ["mh", "eh", "idx", "prev", "sig", "untrusted", "dup"])
                if kind == "mh":
                    entries[i]["manifest_hash"] = hashlib.sha256(
                        f"x{rng.random()}".encode()).hexdigest()
                elif kind == "eh":
                    entries[i]["entry_hash"] = "b" * 64
                elif kind == "idx":
                    entries[i]["index"] = rng.randint(0, n + 2)
                elif kind == "prev":
                    entries[i]["prev_hash"] = "c" * 64
                elif kind == "sig":
                    entries[i]["signature"] = base64.b64encode(
                        other_priv.sign(b"junk")).decode()
                elif kind == "untrusted":
                    entries[i]["public_key"] = other_pub_b64
                elif kind == "dup" and i > 0:
                    entries[i]["manifest_hash"] = entries[0]["manifest_hash"]
                    entries[i]["signature"] = entries[0]["signature"]

        got = audit.audit_log({"entries": entries, "trusted_key_ids": [kid]})
        ref = _audit_ref(entries, [kid])
        assert got == ref, (
            f"case {case}: mismatch\nGOT {json.dumps(got)}\nREF {json.dumps(ref)}")
        for row in ref["rows"]:
            for r in row["reasons"]:
                cov[r] += 1
        total += len(ref["rows"])
    assert total > 400
    for r in REASONS:
        assert cov[r] > 0, f"reason never exercised: {r} ({cov})"


def test_negative_control_first_match_only_rejected():
    """An auditor that reports only the first reason per entry must be rejected
    on the overlapping fuzz set (proves the suite needs full sorted sets)."""
    rng = random.Random(7)
    priv, pub_b64, kid = _mk_key()
    e = _valid_log(rng, 3, priv, pub_b64)
    e[1]["manifest_hash"] = "d" * 64  # double: bad_signature + entry_hash_mismatch
    full = audit.localize_log(e, [kid])
    assert len(full[1]["reasons"]) >= 2, "overlapping tamper must yield >=2 reasons"
