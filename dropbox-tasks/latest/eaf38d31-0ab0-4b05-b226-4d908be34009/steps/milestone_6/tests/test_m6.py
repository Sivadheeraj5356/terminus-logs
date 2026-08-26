"""Milestone 6 grader — recovered CT-log entry leaf-canonicalization (v4).

Grades entrycanon.{canonicalize_entry, signed_input, signed_scope, leaf_hash}
against:
  * the shipped worked-example golden bytes (byte-exact),
  * a held-out test-private golden corpus (byte-exact + Ed25519 verify),
  * an INDEPENDENT re-derivation over a fresh fuzz corpus (functional),
  * negative controls (careful-but-wrong variants) — each must diverge,
  * out-of-scope-mutation invariance, subject canonicalization, epoch
    normalization, conditional projection (sufficiency anchors),
  * a SUFFICIENCY GATE asserting the shipped examples UNIQUELY determine the
    rule (every wrong variant is contradicted by >= 2 shipped examples),
  * the documented CLI surface (real subprocess).

The TRUE rule is a CONJUNCTION of several interacting, non-obvious axes
(conditional field projection, reserved-prefix exclusion with a carve-out,
IDNA + reversed-label + depth-tiebreak + wildcard-last subject ordering,
epoch milliseconds, a leaf_type-keyed payload hash, and a second
domain-separated signed input). It is never stated; only worked examples ship.
"""
import base64
import functools
import hashlib
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/app/transparency")

import _oracle as o  # noqa: E402
import entrycanon  # noqa: E402

ENTRYCANON_PY = os.path.abspath(entrycanon.__file__)

# Test-private golden corpus (held-out; NEVER shipped into /app).
CORPUS = os.path.join(os.path.dirname(__file__), "corpus")

# The agent-facing shipped evidence (the worked examples copied into /app).
_SHIPPED = next(
    (p for p in ("/app/transparency/entrylog/examples",
                 os.path.join(os.path.dirname(__file__), "..", "..", "..",
                              "environment", "provided", "entrylog",
                              "examples"))
     if os.path.isdir(p)), None)

FUZZ_SEEDS = list(range(72))
CONTROL_SEEDS = 72

LEAF_TYPES = ["x509_entry", "precert_entry"]
TLDS = ["com", "org", "net", "io", "dev"]
SLDS = ["example", "acme", "globex", "initech", "umbrella"]
ISSUERS = ["intermediate-CA-7", "root-CA-eu", "CA-shard-9", "issuer-x", "ca-1"]
ORIGINS = ["shard-east-1", "shard-west-3", "shard-eu-2", "edge-9", "ingest-0"]
IDN_LABELS = ["café", "münchen", "naïve", "köln", "über"]
LOG_ID = "ct.transparency.example/2026q1"


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# fuzz entry builder (DIFFERENT seeds than the shipped corpus generator)
# --------------------------------------------------------------------------- #


def _name(rng):
    sld = rng.choice(SLDS)
    tld = rng.choice(TLDS)
    if rng.random() < 0.15:
        return f"*.{sld}.{tld}"
    if rng.random() < 0.12:
        return f"{sld}.{tld}"
    host = rng.choice(["www", "api", "cdn", "mail", "shop", "ns1", "a", "b"])
    if rng.random() < 0.10:
        return f"{rng.choice(IDN_LABELS)}.{sld}.{tld}"
    if rng.random() < 0.10:
        return f"{host}.sub.{sld}.{tld}"
    return f"{host}.{sld}.{tld}"


def _subject(rng):
    names = [_name(rng) for _ in range(rng.randint(1, 5))]
    if rng.random() < 0.4 and names:
        names.append(rng.choice(names).upper())
    rng.shuffle(names)
    if len(names) == 1 and rng.random() < 0.3:
        return names[0]
    return names


def _ts(rng):
    base = (f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
            f"T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}"
            f":{rng.randint(0, 59):02d}")
    if rng.random() < 0.5:
        return base + f".{rng.randint(1, 999):03d}Z"
    return base + "Z"


def _mk_entry(rng):
    lt = rng.choice(LEAF_TYPES)
    e = {
        "log_id": LOG_ID,
        "index": rng.randint(0, 9_000_000),
        "leaf_type": lt,
        "subject": _subject(rng),
        "issued_at": _ts(rng),
        "payload": "cert:" + base64.b64encode(
            rng.getrandbits(256).to_bytes(32, "big")).decode(),
        "received_at": _ts(rng),
    }
    # precerts ALWAYS carry an issuer_id (signed for them); x509 ~half the time
    # (excluded from x509 scope -> an out-of-scope-mutation invariance anchor).
    if lt == "precert_entry" or rng.random() < 0.5:
        e["issuer_id"] = rng.choice(ISSUERS)
    if rng.random() < 0.85:
        e["x_shard"] = rng.randint(0, 31)
    if rng.random() < 0.6:
        e["x_ingest_host"] = rng.choice(["frontend-1", "frontend-2", "edge-9"])
    if rng.random() < 0.5:
        e["x_origin"] = rng.choice(ORIGINS)
    if rng.random() < 0.6:
        e["audit"] = {"reviewer": rng.choice(["a", "b", "c"]), "note": "x"}
    return e


# --------------------------------------------------------------------------- #
# 1. byte-exact against the shipped worked examples + held-out goldens
# --------------------------------------------------------------------------- #


def test_surface():
    """entrycanon exposes canonicalize_entry, signed_input, signed_scope and leaf_hash."""
    for fn in ("canonicalize_entry", "signed_input", "signed_scope",
               "leaf_hash"):
        assert callable(getattr(entrycanon, fn)), fn


def test_canonical_bytes_match_shipped_examples():
    """canonicalize_entry, leaf_hash and signed_input reproduce the shipped worked-example goldens byte-for-byte."""
    assert _SHIPPED is not None, "shipped examples dir not found"
    idx = _load(os.path.join(_SHIPPED, "index.json"))
    checked = 0
    for rec in idx["entries"]:
        entry = _load(os.path.join(_SHIPPED, rec["entry"]))
        gold = _load(os.path.join(_SHIPPED, rec["golden"]))
        want = base64.b64decode(gold["canonical_b64"])
        assert entrycanon.canonicalize_entry(entry) == want, rec["id"]
        assert hashlib.sha256(
            entrycanon.canonicalize_entry(entry)).hexdigest() \
            == gold["canonical_sha256"], rec["id"]
        assert entrycanon.leaf_hash(entry) == \
            bytes.fromhex(gold["leaf_hash_hex"]), rec["id"]
        assert entrycanon.signed_input(entry) == \
            base64.b64decode(gold["signed_input_b64"]), rec["id"]
        checked += 1
    assert checked >= 5


def test_canonical_bytes_match_heldout_goldens():
    """Canonical and signed-input bytes match the held-out golden corpus byte-for-byte."""
    idx = _load(os.path.join(CORPUS, "index.json"))
    checked = 0
    for rec in idx["entries"]:
        entry = _load(os.path.join(CORPUS, rec["entry"]))
        gold = _load(os.path.join(CORPUS, rec["golden"]))
        assert entrycanon.canonicalize_entry(entry) == \
            base64.b64decode(gold["canonical_b64"]), rec["id"]
        assert entrycanon.signed_input(entry) == \
            base64.b64decode(gold["signed_input_b64"]), rec["id"]
        checked += 1
    assert checked >= 20


# --------------------------------------------------------------------------- #
# 2. functional fuzz: agent canon == independent oracle on held-out entries
# --------------------------------------------------------------------------- #


def test_canon_matches_independent_oracle():
    """Over fuzzed entries the agent's canonicalization matches the independent oracle for every public function."""
    for seed in FUZZ_SEEDS:
        rng = random.Random(seed * 2654435761 & 0xFFFFFFFF)
        entry = _mk_entry(rng)
        assert entrycanon.canonicalize_entry(entry) == o._canon(entry), \
            f"seed={seed}"
        assert entrycanon.signed_input(entry) == o._signed_input(entry), \
            f"seed={seed}"
        assert entrycanon.leaf_hash(entry) == o._leaf_hash(entry), \
            f"seed={seed}"
        assert entrycanon.signed_scope(entry) == o._signed_scope(entry), \
            f"seed={seed}"


# --------------------------------------------------------------------------- #
# 3. Ed25519 signatures verify over signed_input, and break on tamper
# --------------------------------------------------------------------------- #


def test_signatures_verify_and_break_on_tamper():
    """signed_input verifies under the log key and stops verifying when an in-scope field is tampered."""
    pub = _load(os.path.join(_SHIPPED, "log_public_key.json"))["public_key"]
    idx = _load(os.path.join(_SHIPPED, "index.json"))
    for rec in idx["entries"]:
        entry = _load(os.path.join(_SHIPPED, rec["entry"]))
        gold = _load(os.path.join(_SHIPPED, rec["golden"]))
        sig = gold["signature_b64"]
        assert o._Pub.from_public_bytes(base64.b64decode(pub)).verify(
            base64.b64decode(sig), entrycanon.signed_input(entry)) is None
        # tamper an in-scope field -> signature must NOT verify
        bad = json.loads(json.dumps(entry))
        bad["index"] = (bad["index"] or 0) + 1
        try:
            o._Pub.from_public_bytes(base64.b64decode(pub)).verify(
                base64.b64decode(sig), entrycanon.signed_input(bad))
            verified = True
        except Exception:
            verified = False
        assert verified is False, rec["id"]


# --------------------------------------------------------------------------- #
# 4. sufficiency anchors: out-of-scope invariance, subject, timestamp,
#    conditional projection
# --------------------------------------------------------------------------- #


def test_out_of_scope_mutation_is_invariant():
    """Mutating out-of-scope fields leaves the canonical and signed-input bytes unchanged."""
    for seed in range(20):
        rng = random.Random(900000 + seed)
        entry = _mk_entry(rng)
        base = entrycanon.canonicalize_entry(entry)
        m = json.loads(json.dumps(entry))
        m["received_at"] = "2099-01-01T00:00:00Z"
        m["x_shard"] = 9999
        m["x_new_ext"] = {"deep": [1, 2, 3]}
        m.setdefault("audit", {})["reviewer"] = "tamperer"
        # mutating issuer_id is invariant for x509 (out of scope) entries.
        if entry.get("leaf_type") == "x509_entry":
            m["issuer_id"] = "MUTATED-CA"
        assert entrycanon.canonicalize_entry(m) == base, seed
        assert entrycanon.signed_input(m) == entrycanon.signed_input(entry)


def test_signed_scope_projection_is_conditional():
    """signed_scope projects the conditional in-scope fields, excluding issuer_id for x509 and mapping x_origin to origin."""
    # x509: issuer_id and ordinary x_* excluded; x_origin (if present) -> origin
    x509 = {"log_id": LOG_ID, "index": 5, "leaf_type": "x509_entry",
            "issuer_id": "CA-9", "subject": "x.example.com",
            "issued_at": "2026-01-01T00:00:00Z", "payload": "p",
            "x_shard": 1, "x_origin": "shard-east-1", "received_at": "2030-01-01T00:00:00Z",
            "audit": {"r": "x"}}
    sc = entrycanon.signed_scope(x509)
    assert set(sc) == {"log_id", "leaf_type", "index", "subject",
                       "issued_at", "payload", "origin"}
    assert "issuer_id" not in sc and "x_shard" not in sc
    assert "x_origin" not in sc and "received_at" not in sc and "audit" not in sc
    assert sc["origin"] == "shard-east-1"

    # precert with the SAME fields: issuer_id is now IN scope.
    precert = dict(x509, leaf_type="precert_entry")
    scp = entrycanon.signed_scope(precert)
    assert "issuer_id" in scp and scp["issuer_id"] == "CA-9"
    assert "origin" in scp


def test_issuer_id_conditional_on_leaf_type():
    """issuer_id is in scope for precert entries but dropped for x509 entries."""
    # the same entry as x509 vs precert must differ ONLY by issuer_id presence.
    base = {"log_id": LOG_ID, "index": 7, "subject": "a.example.com",
            "issuer_id": "CA-7", "issued_at": "2026-01-01T00:00:00Z",
            "payload": "p"}
    x509 = entrycanon.canonicalize_entry(dict(base, leaf_type="x509_entry"))
    precert = entrycanon.canonicalize_entry(dict(base, leaf_type="precert_entry"))
    assert b"issuer_id=CA-7" not in x509
    assert b"issuer_id=CA-7" in precert


def test_x_origin_carveout():
    """x_origin is signed as origin while other x_* extension fields are excluded."""
    base = {"log_id": LOG_ID, "index": 9, "leaf_type": "x509_entry",
            "subject": "a.example.com", "issued_at": "2026-01-01T00:00:00Z",
            "payload": "p"}
    without = entrycanon.canonicalize_entry(base)
    withorigin = entrycanon.canonicalize_entry(dict(base, x_origin="shard-z"))
    other_x = entrycanon.canonicalize_entry(dict(base, x_zone="shard-z"))
    assert b"origin=shard-z" in withorigin
    assert without != withorigin       # x_origin IS signed
    assert without == other_x          # other x_* is NOT signed


def test_subject_idna_dedup_reversed_label_depth_wildcard():
    """Subject names are IDNA-encoded, de-duplicated and ordered by reversed labels with depth tiebreak and wildcard-last."""
    entry = {"log_id": LOG_ID, "index": 1, "leaf_type": "x509_entry",
             "subject": ["b.example.org", "A.EXAMPLE.COM", "a.example.com",
                         "*.example.com", "example.com", "köln.example.com"],
             "issued_at": "2026-01-01T00:00:00Z", "payload": "p"}
    canon = entrycanon.canonicalize_entry(entry).decode("utf-8")
    seg = canon.split("subject=")[1].split("\x1e")[0]
    # under .com: concrete leaves (a, köln->xn--, wildcard) sort, wildcard AFTER
    # its concrete siblings, the bare parent example.com LAST (depth tiebreak),
    # then the .org name. A,a dedup to one.
    assert seg == ("a.example.com,xn--kln-sna.example.com,*.example.com,"
                   "example.com,b.example.org"), seg


def test_timestamp_is_epoch_milliseconds():
    """Timestamps are encoded as epoch milliseconds, keeping fractional seconds to ms precision."""
    whole = {"log_id": LOG_ID, "index": 1, "leaf_type": "x509_entry",
             "subject": "x.example.com", "issued_at": "2026-01-15T10:00:00Z",
             "payload": "p"}
    canon = entrycanon.canonicalize_entry(whole).decode("utf-8")
    seg = canon.split("issued_at=")[1].split("\x1e")[0]
    assert seg.endswith("000"), seg            # whole second -> x1000
    assert int(seg) == 1768471200000, seg
    # a fractional part is KEPT to ms precision (NOT dropped)
    frac = dict(whole, issued_at="2026-01-15T10:00:00.250Z")
    cf = entrycanon.canonicalize_entry(frac).decode("utf-8")
    segf = cf.split("issued_at=")[1].split("\x1e")[0]
    assert int(segf) == 1768471200250, segf


def test_payload_hash_is_keyed_by_leaf_type():
    """The payload hash is domain-separated by leaf_type, so identical payloads hash differently across types."""
    base = {"log_id": LOG_ID, "index": 1, "subject": "x.example.com",
            "issued_at": "2026-01-01T00:00:00Z", "payload": "same-bytes",
            "issuer_id": "CA-1"}
    px = entrycanon.canonicalize_entry(dict(base, leaf_type="x509_entry"))
    pp = entrycanon.canonicalize_entry(dict(base, leaf_type="precert_entry"))
    hx = px.split(b"payload=")[1].split(b"\x1e")[0]
    hp = pp.split(b"payload=")[1].split(b"\x1e")[0]
    # same payload bytes hash DIFFERENTLY under the two leaf types
    assert hx != hp
    # and neither equals the bare sha256 of the payload
    bare = hashlib.sha256(b"same-bytes").hexdigest().encode()
    assert hx != bare and hp != bare


def test_payload_hash_input_matches_shipped_evidence():
    """The recovered payload hex matches sha256 of the shipped payload_hash_input pre-image."""
    # The shipped goldens expose, for each worked example, the exact pre-image
    # bytes whose sha256 IS the payload hex inside the canonical bytes
    # (payload_hash_input_b64). The recovered canonicalization must reproduce
    # the very same payload hex, i.e. it must hash the same pre-image the log
    # hashed. This pins the payload sub-encoding (which the canonical bytes
    # alone leave behind a one-way hash) from the evidence, not from guessing.
    assert _SHIPPED is not None
    idx = _load(os.path.join(_SHIPPED, "index.json"))
    checked = 0
    for rec in idx["entries"]:
        entry = _load(os.path.join(_SHIPPED, rec["entry"]))
        gold = _load(os.path.join(_SHIPPED, rec["golden"]))
        pre = base64.b64decode(gold["payload_hash_input_b64"])
        want_hex = hashlib.sha256(pre).hexdigest().encode()
        canon = entrycanon.canonicalize_entry(entry)
        body = canon[len(o._DOMAIN):].rstrip(b"\n")
        seg = next(p[len(b"payload="):] for p in body.split(o._RS)
                   if p.startswith(b"payload="))
        assert seg == want_hex, rec["id"]
        checked += 1
    assert checked >= 5


def test_index_zero_padded_width16():
    """The index field is rendered zero-padded to width 16."""
    entry = {"log_id": LOG_ID, "index": 42, "leaf_type": "x509_entry",
             "subject": "x.example.com", "issued_at": "2026-01-01T00:00:00Z",
             "payload": "p"}
    canon = entrycanon.canonicalize_entry(entry).decode("utf-8")
    seg = canon.split("index=")[1].split("\x1e")[0]
    assert seg == "0000000000000042", seg


# --------------------------------------------------------------------------- #
# 5. negative controls — each careful-but-wrong canon must diverge.
# Defined over the TRUE oracle so they are independent of the agent module.
# --------------------------------------------------------------------------- #


def _parts_with(entry, override):
    parts = []
    for k, s in o._scope_keys(entry):
        if k in override:
            parts.append(override[k](entry))
        else:
            parts.append(k.encode() + b"=" + o._field_value(k, s, entry))
    return o._DOMAIN + o._RS.join(parts) + b"\n"


def _ctrl_alpha_order(entry):
    pairs = sorted(o._scope_keys(entry), key=lambda p: p[0])
    parts = [k.encode() + b"=" + o._field_value(k, s, entry) for k, s in pairs]
    return o._DOMAIN + o._RS.join(parts) + b"\n"


def _ctrl_plain_subject_sort(entry):
    def sub(e):
        subj = e.get("subject")
        names = [subj] if isinstance(subj, str) else list(subj or [])
        uniq = sorted(dict.fromkeys(o._puny_name(n) for n in names))
        return b"subject=" + ",".join(uniq).encode()
    return _parts_with(entry, {"subject": sub})


def _ctrl_no_depth_tiebreak(entry):
    def sub(e):
        subj = e.get("subject")
        names = [subj] if isinstance(subj, str) else list(subj or [])
        uniq = list(dict.fromkeys(o._puny_name(n) for n in names))
        uniq.sort(key=lambda n: o._rev_labels(n))
        return b"subject=" + ",".join(uniq).encode()
    return _parts_with(entry, {"subject": sub})


def _ctrl_wildcard_first(entry):
    def keyf(n):
        labs = n.split(".")
        return ["" if lab == "*" else lab for lab in reversed(labs)]

    def sub(e):
        subj = e.get("subject")
        names = [subj] if isinstance(subj, str) else list(subj or [])
        uniq = list(dict.fromkeys(o._puny_name(n) for n in names))
        uniq.sort(key=keyf)
        return b"subject=" + ",".join(uniq).encode()
    return _parts_with(entry, {"subject": sub})


def _ctrl_no_idna(entry):
    def sub(e):
        subj = e.get("subject")
        names = [subj] if isinstance(subj, str) else list(subj or [])
        uniq = list(dict.fromkeys(n.lower() for n in names))
        uniq.sort(key=functools.cmp_to_key(o._cmp_names))
        return b"subject=" + ",".join(uniq).encode("utf-8")
    return _parts_with(entry, {"subject": sub})


def _ctrl_no_dedup_subject(entry):
    def sub(e):
        subj = e.get("subject")
        names = [subj] if isinstance(subj, str) else list(subj or [])
        names = [o._puny_name(n) for n in names]
        names.sort(key=functools.cmp_to_key(o._cmp_names))
        return b"subject=" + ",".join(names).encode()
    return _parts_with(entry, {"subject": sub})


def _ctrl_epoch_seconds(entry):
    def ts(e):
        return b"issued_at=" + str(o._epoch_millis(e.get("issued_at")) // 1000).encode()
    return _parts_with(entry, {"issued_at": ts})


def _ctrl_keep_rfc3339(entry):
    def ts(e):
        return b"issued_at=" + str(e.get("issued_at")).encode()
    return _parts_with(entry, {"issued_at": ts})


def _ctrl_raw_index(entry):
    def ix(e):
        return b"index=" + str(e.get("index")).encode()
    return _parts_with(entry, {"index": ix})


def _ctrl_plain_payload(entry):
    def pl(e):
        return b"payload=" + hashlib.sha256(
            e.get("payload").encode()).hexdigest().encode()
    return _parts_with(entry, {"payload": pl})


def _ctrl_payload_not_keyed(entry):
    def pl(e):
        return b"payload=" + hashlib.sha256(
            o._PAYLOAD_DOMAIN + e.get("payload").encode()).hexdigest().encode()
    return _parts_with(entry, {"payload": pl})


def _ctrl_include_issuer_always(entry):
    pairs = []
    for k in o._BASE_ORDER:
        pairs.append((k, k))
        if k == "leaf_type" and "issuer_id" in entry:
            pairs.append(("issuer_id", "issuer_id"))
    if "x_origin" in entry:
        pairs.append(("origin", "x_origin"))
    parts = [k.encode() + b"=" + o._field_value(k, s, entry) for k, s in pairs]
    return o._DOMAIN + o._RS.join(parts) + b"\n"


def _ctrl_drop_issuer_always(entry):
    pairs = [(k, k) for k in o._BASE_ORDER]
    if "x_origin" in entry:
        pairs.append(("origin", "x_origin"))
    parts = [k.encode() + b"=" + o._field_value(k, s, entry) for k, s in pairs]
    return o._DOMAIN + o._RS.join(parts) + b"\n"


def _ctrl_exclude_origin(entry):
    pairs = []
    for k in o._BASE_ORDER:
        pairs.append((k, k))
        if k == "leaf_type" and entry.get("leaf_type") == "precert_entry":
            pairs.append(("issuer_id", "issuer_id"))
    parts = [k.encode() + b"=" + o._field_value(k, s, entry) for k, s in pairs]
    return o._DOMAIN + o._RS.join(parts) + b"\n"


def _ctrl_origin_keep_prefix(entry):
    def org(e):
        return b"x_origin=" + e.get("x_origin").encode()
    return _parts_with(entry, {"origin": org})


def _ctrl_include_received_at(entry):
    body = o._canon(entry)[:-1]
    return body + o._RS + b"received_at=" + \
        str(entry.get("received_at", "")).encode() + b"\n"


def _ctrl_no_prefix(entry):
    return o._canon(entry)[len(o._DOMAIN):]


def _ctrl_sign_canon_directly(entry):
    return o._canon(entry)


_CANON_CONTROLS = {
    "alpha-field-order": _ctrl_alpha_order,
    "plain-subject-sort": _ctrl_plain_subject_sort,
    "no-depth-tiebreak": _ctrl_no_depth_tiebreak,
    "wildcard-sorts-first": _ctrl_wildcard_first,
    "no-idna-punycode": _ctrl_no_idna,
    "no-subject-dedup": _ctrl_no_dedup_subject,
    "epoch-seconds-not-ms": _ctrl_epoch_seconds,
    "keep-rfc3339-string": _ctrl_keep_rfc3339,
    "raw-index": _ctrl_raw_index,
    "plain-payload-sha256": _ctrl_plain_payload,
    "payload-not-keyed-by-leaftype": _ctrl_payload_not_keyed,
    "include-issuer-always": _ctrl_include_issuer_always,
    "drop-issuer-always": _ctrl_drop_issuer_always,
    "exclude-x-origin": _ctrl_exclude_origin,
    "origin-keep-x-prefix": _ctrl_origin_keep_prefix,
    "include-received-at": _ctrl_include_received_at,
    "no-domain-prefix": _ctrl_no_prefix,
}


def _divergence(control, seeds=CONTROL_SEEDS, mk=_mk_entry, base=40503):
    diverged = total = 0
    for seed in range(seeds):
        rng = random.Random(seed * base & 0xFFFFFFFF)
        entry = mk(rng)
        total += 1
        try:
            got = entrycanon.canonicalize_entry(entry)
        except Exception:
            continue
        if control(entry) != got:
            diverged += 1
    return diverged, total


# Structural controls fire on (nearly) every entry.
def test_control_alpha_order_diverges():
    """An alphabetical-field-order variant diverges from the recovered canonicalization on nearly every entry."""
    d, t = _divergence(_ctrl_alpha_order)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_raw_index_diverges():
    """A raw non-zero-padded index variant diverges on nearly every entry."""
    d, t = _divergence(_ctrl_raw_index)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_no_prefix_diverges():
    """Dropping the domain prefix diverges on nearly every entry."""
    d, t = _divergence(_ctrl_no_prefix)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_epoch_seconds_diverges():
    """Encoding timestamps as epoch seconds instead of milliseconds diverges on nearly every entry."""
    d, t = _divergence(_ctrl_epoch_seconds)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_keep_rfc3339_diverges():
    """Keeping the raw RFC 3339 timestamp string diverges on nearly every entry."""
    d, t = _divergence(_ctrl_keep_rfc3339)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_plain_payload_diverges():
    """A plain non-keyed payload sha256 diverges on nearly every entry."""
    d, t = _divergence(_ctrl_plain_payload)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_payload_not_keyed_diverges():
    """A payload hash not keyed by leaf_type diverges on nearly every entry."""
    d, t = _divergence(_ctrl_payload_not_keyed)
    assert d / t >= 0.99, f"{d}/{t}"


def test_control_include_received_at_diverges():
    """Including the out-of-scope received_at field diverges on nearly every entry."""
    d, t = _divergence(_ctrl_include_received_at)
    assert d / t >= 0.99, f"{d}/{t}"


# Subject controls fire when the subject exercises the axis (use crafted entries).
def test_control_plain_subject_sort_diverges():
    """A plain lexical subject sort diverges wherever the subject exercises the ordering axis."""
    d, t = _divergence(_ctrl_plain_subject_sort)
    assert d / t >= 0.15, f"{d}/{t}"


def test_control_no_depth_tiebreak_diverges():
    """Omitting the subject depth tiebreak diverges on the crafted parent/child subject sets."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(70000 + seed)
        entry = _mk_entry(rng)
        entry["subject"] = ["a.acme.com", "acme.com", "b.sub.acme.com",
                            "sub.acme.com"]
        total += 1
        if _ctrl_no_depth_tiebreak(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_wildcard_first_diverges():
    """Sorting wildcard subjects before their concrete siblings diverges on the crafted wildcard sets."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(71000 + seed)
        entry = _mk_entry(rng)
        entry["subject"] = ["*.acme.com", "a.acme.com", "www.acme.com"]
        total += 1
        if _ctrl_wildcard_first(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_no_idna_diverges():
    """Skipping IDNA/punycode encoding of subjects diverges on the crafted IDN sets."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(72000 + seed)
        entry = _mk_entry(rng)
        entry["subject"] = ["café.acme.com", "münchen.globex.io", "a.acme.com"]
        total += 1
        if _ctrl_no_idna(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_no_subject_dedup_diverges():
    """Not de-duplicating subject names diverges on the crafted duplicate sets."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(73000 + seed)
        entry = _mk_entry(rng)
        entry["subject"] = ["a.example.com", "A.EXAMPLE.COM", "b.acme.org"]
        total += 1
        if _ctrl_no_dedup_subject(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


# Projection controls fire on entries that carry the relevant field.
def test_control_include_issuer_always_diverges():
    """Always including issuer_id even for x509 diverges on crafted x509 entries carrying one."""
    # craft x509 entries that DO carry an issuer_id (which must be dropped).
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(74000 + seed)
        entry = _mk_entry(rng)
        entry["leaf_type"] = "x509_entry"
        entry["issuer_id"] = "CA-craft"
        total += 1
        if _ctrl_include_issuer_always(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_drop_issuer_always_diverges():
    """Always dropping issuer_id even for precert diverges on crafted precert entries."""
    # craft precert entries (issuer_id must be INCLUDED).
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(75000 + seed)
        entry = _mk_entry(rng)
        entry["leaf_type"] = "precert_entry"
        entry["issuer_id"] = "CA-craft"
        total += 1
        if _ctrl_drop_issuer_always(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_exclude_origin_diverges():
    """Excluding x_origin/origin diverges on entries that carry x_origin."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(76000 + seed)
        entry = _mk_entry(rng)
        entry["x_origin"] = "shard-craft"
        total += 1
        if _ctrl_exclude_origin(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_origin_keep_prefix_diverges():
    """Keeping the x_ prefix on origin diverges on entries that carry x_origin."""
    diverged = total = 0
    for seed in range(40):
        rng = random.Random(77000 + seed)
        entry = _mk_entry(rng)
        entry["x_origin"] = "shard-craft"
        total += 1
        if _ctrl_origin_keep_prefix(entry) != entrycanon.canonicalize_entry(entry):
            diverged += 1
    assert total >= 5 and diverged / total >= 0.99, f"{diverged}/{total}"


def test_control_sign_canon_directly_diverges():
    """Signing the canonical bytes directly, without the domain-separated framing, diverges from signed_input on nearly every entry."""
    diverged = total = 0
    for seed in range(CONTROL_SEEDS):
        rng = random.Random(seed * 40503 & 0xFFFFFFFF)
        entry = _mk_entry(rng)
        total += 1
        if _ctrl_sign_canon_directly(entry) != entrycanon.signed_input(entry):
            diverged += 1
    assert diverged / total >= 0.99, f"{diverged}/{total}"


# --------------------------------------------------------------------------- #
# 6. SUFFICIENCY GATE — the SHIPPED worked examples uniquely determine the rule.
# Each careful-but-wrong variant must be contradicted by >= 2 shipped examples
# (so a careful agent can INFER, not guess, each axis from the evidence alone).
# --------------------------------------------------------------------------- #


def test_shipped_examples_uniquely_determine_the_rule():
    """The shipped worked examples rule out every careful-but-wrong variant, uniquely pinning the canonicalization."""
    assert _SHIPPED is not None
    idx = _load(os.path.join(_SHIPPED, "index.json"))
    worked = []
    for rec in idx["entries"]:
        entry = _load(os.path.join(_SHIPPED, rec["entry"]))
        gold = _load(os.path.join(_SHIPPED, rec["golden"]))
        worked.append((rec["id"], entry, base64.b64decode(gold["canonical_b64"])))
    assert len(worked) >= 5, len(worked)

    # (a) the agent reproduces every shipped example byte-exact.
    for cid, entry, want in worked:
        assert entrycanon.canonicalize_entry(entry) == want, cid

    # (b) each canon control is ruled out by >= 2 shipped examples.
    for name, ctrl in _CANON_CONTROLS.items():
        contradicting = sum(
            1 for _cid, entry, want in worked if ctrl(entry) != want)
        assert contradicting >= 2, (
            f"shipped examples do not pin the '{name}' axis "
            f"(only {contradicting} contradict it)")

    # (c) the signed-input framing is ruled out by every shipped example.
    sign_contra = sum(
        1 for _cid, entry, _want in worked
        if _ctrl_sign_canon_directly(entry) != entrycanon.signed_input(entry))
    assert sign_contra >= 5, sign_contra


# --------------------------------------------------------------------------- #
# 7. CLI surface — real subprocess for both subcommands.
# --------------------------------------------------------------------------- #


def test_cli_canonicalize_and_signed_input(tmp_path):
    """The entrycanon CLI canonicalize and signed-input subcommands write bytes matching the module functions."""
    entry_path = os.path.join(_SHIPPED, "entry_01.json")
    entry = _load(entry_path)
    out_canon = tmp_path / "canon.bin"
    out_sig = tmp_path / "sigin.bin"
    p1 = subprocess.run(
        [sys.executable, ENTRYCANON_PY, "canonicalize",
         "--entry", entry_path, "--out", str(out_canon)],
        capture_output=True, text=True, timeout=60)
    assert p1.returncode == 0, p1.stderr
    assert out_canon.read_bytes() == entrycanon.canonicalize_entry(entry)
    p2 = subprocess.run(
        [sys.executable, ENTRYCANON_PY, "signed-input",
         "--entry", entry_path, "--out", str(out_sig)],
        capture_output=True, text=True, timeout=60)
    assert p2.returncode == 0, p2.stderr
    assert out_sig.read_bytes() == entrycanon.signed_input(entry)
