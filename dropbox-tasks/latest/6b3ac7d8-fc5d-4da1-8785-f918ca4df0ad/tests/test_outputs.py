"""End-to-end verifier for the vaultseal Terraform triage module.

These tests never look at the agent's analysis code. They generate fresh, seeded
gdb/valgrind corpora at test time, apply the agent's module at /app/triage
against them, and compare the produced triage_report.json against an independent
reference implementation of the runbook. Because the corpora are hidden and
regenerated per run, the report cannot be hardcoded or precomputed.
"""
import glob
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import tempfile
import time

import pytest

MODULE_DIR = "/app/triage"

# A full fuzz run yields tens of thousands of cases and the analysis must finish
# in well under a minute (see the runbook's "Performance and scale" section). A
# naive all-pairs O(n^2) clustering takes several minutes at this size; a correct
# near-linear implementation finishes in a couple of seconds.
PERF_CASES = 15000
PERF_BUDGET_SEC = 60

# --------------------------------------------------------------------------- #
# Independent reference implementation of TRIAGE_RUNBOOK.md                    #
# --------------------------------------------------------------------------- #
CRYPTO_OPS = {
    "aes256_gcm_seal": {"secret": True, "key_bits": 256},
    "aes256_gcm_open": {"secret": False, "key_bits": 256},
    "rsa2048_sign": {"secret": True, "key_bits": 2048},
    "rsa2048_verify": {"secret": False, "key_bits": 2048},
    "ec_p256_sign": {"secret": True, "key_bits": 256},
    "ec_p256_verify": {"secret": False, "key_bits": 256},
    "hkdf_derive": {"secret": True, "key_bits": 256},
    "hmac_sha256": {"secret": False, "key_bits": 256},
}
SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RANK_SEV = {v: k for k, v in SEV_RANK.items()}
MEM_ERR = {"use-after-free", "invalid-read", "invalid-write", "invalid-free"}
VALID_KEY_HEX = {32, 48, 64}
KEY_RE = re.compile(r"(?:0x)?(?:[0-9a-fA-F]{2}[ \t:]?){16,}")
GDB_FRAME_RE = re.compile(
    r"^\s*#\d+\s+(?:0x[0-9a-fA-F]+\s+in\s+)?([A-Za-z_]\w*)\s*\(.*?\)\s+at\s+([^:\s]+):(\d+)"
)
VG_FRAME_RE = re.compile(r"(?:at|by)\s+0x[0-9a-fA-F]+:\s*([A-Za-z_]\w*)\s*\(")


def _norm_hex(s):
    s = s.strip()
    if s[:2].lower() == "0x":
        s = s[2:]
    return re.sub(r"[ \t:]", "", s).lower()


def _is_key(h):
    if len(h) not in VALID_KEY_HEX:
        return False
    try:
        b = bytes.fromhex(h)
    except ValueError:
        return False
    x = 0
    for c in b[:-1]:
        x ^= c
    return x == b[-1]


def _fp(salt, h):
    return "vsk1:" + hashlib.sha256((salt + ":" + h).encode()).hexdigest()[:8]


def _collapse(frames):
    out = []
    for f in frames:
        if not out or out[-1] != f:
            out.append(f)
    return out


def _edit_distance(a, b):
    lb = len(b)
    if a == b:
        return 0
    prev = list(range(lb + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def _connected(sig_by_case):
    ids = sorted(sig_by_case)
    parent = {c: c for c in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if _edit_distance(sig_by_case[ids[i]], sig_by_case[ids[j]]) <= 1:
                union(ids[i], ids[j])
    return {c: find(c) for c in ids}


def _canon(raw, stem):
    for src in (raw, stem):
        if not src:
            continue
        m = re.search(r"(\d+)", src)
        if m:
            return "%04d" % int(m.group(1))
    base = re.sub(r"[^A-Za-z0-9]+", "_", (raw or stem or "unknown").strip()).strip("_")
    return base or "unknown"


def _parse_gdb(text):
    signal = raw_case = None
    frames = []
    for line in text.splitlines():
        m = re.match(r"\s*signal:\s*(\S+)", line)
        if m and signal is None:
            signal = m.group(1)
        m = re.match(r"\s*case:\s*(.+)", line)
        if m and raw_case is None:
            raw_case = m.group(1).strip()
        m = GDB_FRAME_RE.match(line)
        if m:
            frames.append("%s at %s:%s" % (m.group(1), m.group(2), m.group(3)))
    frames = _collapse(frames)
    op = next((f.split(" at ", 1)[0] for f in frames if f.split(" at ", 1)[0] in CRYPTO_OPS), None)
    return {"raw_case": raw_case, "signal": signal, "frames": frames, "op": op, "text": text}


def _parse_vg(text):
    raw_case = None
    for line in text.splitlines():
        m = re.search(r"case:\s*(\S+)", line)
        if m and raw_case is None:
            raw_case = m.group(1).strip()
    low = text.lower()
    freed = "free'd" in low or "freed" in low
    r, w = "invalid read" in low, "invalid write" in low
    if (r or w) and freed:
        ec = "use-after-free"
    elif "invalid free" in low or "mismatched free" in low:
        ec = "invalid-free"
    elif r:
        ec = "invalid-read"
    elif w:
        ec = "invalid-write"
    elif "uninitialised" in low or "uninitialized" in low:
        ec = "uninitialized-value"
    else:
        ec = "unknown"
    op = next((m.group(1) for m in VG_FRAME_RE.finditer(text) if m.group(1) in CRYPTO_OPS), None)
    return {"raw_case": raw_case, "error_class": ec, "op": op, "text": text}


def _classify(secret, ec, leaked, shared):
    if leaked and secret:
        return "critical"
    if leaked and (not secret) and shared:
        return "critical"
    if leaked and not secret:
        return "high"
    if secret and ec in MEM_ERR:
        return "high"
    if (not secret) and ec in MEM_ERR:
        return "medium"
    if secret and ec == "uninitialized-value":
        return "medium"
    return "low"


def _redact(text, salt):
    def repl(m):
        h = _norm_hex(m.group(0))
        return _fp(salt, h) if _is_key(h) else "vsx1:" + hashlib.sha256(("nonkey:" + h).encode()).hexdigest()[:8]
    return KEY_RE.sub(repl, text)


def reference_report(corpus_dir, salt="vaultseal", gate="high"):
    gdb, valg = {}, {}
    for p in sorted(glob.glob(os.path.join(corpus_dir, "gdb", "*"))):
        if os.path.isfile(p):
            d = _parse_gdb(open(p, encoding="utf-8", errors="replace").read())
            gdb[_canon(d["raw_case"], os.path.splitext(os.path.basename(p))[0])] = d
    for p in sorted(glob.glob(os.path.join(corpus_dir, "valgrind", "*"))):
        if os.path.isfile(p):
            d = _parse_vg(open(p, encoding="utf-8", errors="replace").read())
            valg[_canon(d["raw_case"], os.path.splitext(os.path.basename(p))[0])] = d

    case_ids = set(gdb) | set(valg)

    case_keys, key_cases = {}, {}
    for cid in case_ids:
        g, v = gdb.get(cid), valg.get(cid)
        combined = (g["text"] if g else "") + "\n" + (v["text"] if v else "")
        keys = sorted({_norm_hex(m) for m in KEY_RE.findall(combined) if _is_key(_norm_hex(m))})
        case_keys[cid] = keys
        for k in keys:
            key_cases.setdefault(k, set()).add(cid)

    sig_by_case = {}
    for cid in case_ids:
        g = gdb.get(cid)
        sig_by_case[cid] = ([f.split(" at ", 1)[0] for f in g["frames"]]
                            if (g and g["frames"]) else ["<unknown>"])
    root_of = _connected(sig_by_case)

    findings = []
    for cid in case_ids:
        g, v = gdb.get(cid), valg.get(cid)
        op_g = g["op"] if g else None
        op_v = v["op"] if v else None
        op = op_g or op_v
        ec = v["error_class"] if v else "unknown"
        keys = case_keys[cid]
        leaked = bool(keys)
        shared = any(len(key_cases[k]) >= 2 for k in keys)
        leak_context = None
        if leaked:
            combined = (g["text"] if g else "") + "\n" + (v["text"] if v else "")
            for line in combined.splitlines():
                if any(_is_key(_norm_hex(m)) for m in KEY_RE.findall(line)):
                    leak_context = _redact(line.strip(), salt)
                    break
        secret = CRYPTO_OPS.get(op, {}).get("secret", False)
        frames = g["frames"] if g else []
        findings.append({
            "case_id": cid,
            "operation": op,
            "operation_conflict": bool(op_g and op_v and op_g != op_v),
            "error_class": ec,
            "crash_signal": g["signal"] if g else None,
            "key_bits": CRYPTO_OPS[op]["key_bits"] if op in CRYPTO_OPS else None,
            "leaked": leaked,
            "shared_key": bool(leaked and shared),
            "leaked_key_fingerprint": _fp(salt, keys[0]) if leaked else None,
            "leak_context": leak_context,
            "severity": _classify(secret, ec, leaked, shared),
            "correlated": bool(g and v),
            "_root": root_of[cid],
            "gdb_frames": [_redact(f, salt) for f in frames[:6]],
        })

    members = {}
    for f in findings:
        members.setdefault(f["_root"], []).append(f)
    cluster_by_root = {}
    for root, ms in members.items():
        member_ids = sorted(m["case_id"] for m in ms)
        cluster_by_root[root] = {
            "cluster_id": "clu:" + hashlib.sha256("|".join(member_ids).encode()).hexdigest()[:8],
            "signature": sig_by_case[member_ids[0]][:3],
            "size": len(ms),
            "severity": RANK_SEV[max(SEV_RANK[m["severity"]] for m in ms)],
            "representative": member_ids[0],
        }
    for f in findings:
        f["cluster_id"] = cluster_by_root[f.pop("_root")]["cluster_id"]

    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], f["case_id"]))
    clusters = list(cluster_by_root.values())
    clusters.sort(key=lambda c: (-SEV_RANK[c["severity"]], c["cluster_id"]))
    counts = {s: 0 for s in SEV_RANK}
    for f in findings:
        counts[f["severity"]] += 1
    max_rank = max((SEV_RANK[f["severity"]] for f in findings), default=None)
    gated = max_rank is not None and max_rank >= SEV_RANK.get(gate, SEV_RANK["high"])
    return {
        "schema_version": "1.0",
        "generated_by": "vaultseal-triage",
        "severity_gate": gate,
        "gated": gated,
        "max_severity": RANK_SEV[max_rank] if max_rank is not None else None,
        "severity_counts": counts,
        "corpus": {"gdb_cases": len(gdb), "valgrind_cases": len(valg),
                   "correlated": len(set(gdb) & set(valg)), "clusters": len(clusters),
                   "total_findings": len(findings)},
        "clusters": clusters,
        "findings": findings,
    }


# --------------------------------------------------------------------------- #
# Fixture corpus generators                                                   #
# --------------------------------------------------------------------------- #
SECRET_OPS = ["aes256_gcm_seal", "rsa2048_sign", "ec_p256_sign", "hkdf_derive"]
PUBLIC_OPS = ["aes256_gcm_open", "rsa2048_verify", "ec_p256_verify", "hmac_sha256"]
ALL_OPS = SECRET_OPS + PUBLIC_OPS
OP_LINE = {op: 100 + 30 * i for i, op in enumerate(ALL_OPS)}
ERRS = ["invalid-read", "invalid-write", "use-after-free", "invalid-free", "uninitialized-value"]
HELPERS = ["seal_record", "open_record", "derive_ctx", "hash_block", "load_key",
           "verify_tag", "stage_one", "stage_two", "emit_out", "wrap_buffer"]


def _addr(rng):
    return "0x%012x" % rng.randrange(0x555500000000, 0x5555ffffffff)


def _valid_key(rng, nbytes, zero=False):
    body = [0] * (nbytes - 1) if zero else [rng.randrange(256) for _ in range(nbytes - 1)]
    chk = 0
    for c in body:
        chk ^= c
    return "".join("%02x" % b for b in body + [chk])


def _decoy(rng, kind):
    if kind == 0:
        return "".join("%02x" % rng.randrange(256) for _ in range(20))
    body = [rng.randrange(256) for _ in range(31)]
    chk = 0
    for c in body:
        chk ^= c
    return "".join("%02x" % b for b in body + [(chk ^ 0x5A) & 0xFF])


def _enc(rng, style, raw):
    pairs = [raw[i:i + 2] for i in range(0, len(raw), 2)]
    if style == 0:
        return raw
    if style == 1:
        return ":".join(pairs)
    if style == 2:
        return "0x" + " ".join(pairs)
    if style == 3:
        seps = [rng.choice(["", ":", " ", "\t"]) for _ in pairs]
        return "".join(p + s for p, s in zip(pairs, seps)).rstrip()
    return raw.upper()


def _gdb_from_funcs(rng, case, signal, funcs, key):
    L = ["vaultseal triage snapshot", "case: %s" % case]
    if signal:
        L.append("signal: %s (fault)" % signal)
    for i, (fn, ln) in enumerate(funcs):
        L.append("#%d  %s in %s (a=%s) at vaultseal.c:%d" % (i, _addr(rng), fn, _addr(rng), ln))
    if key is not None:
        L.append("key: %s" % key)
    return "\n".join(L) + "\n"


def _gdb(rng, case, op, signal, key, malformed):
    funcs = ([(op, OP_LINE[op])] if op else []) + [("seal_record", 400 + rng.randrange(20)), ("main", 512)]
    if malformed:
        L = ["vaultseal triage snapshot", "case: %s" % case]
        if signal:
            L.append("signal: %s (fault)" % signal)
        for i, (fn, ln) in enumerate(funcs):
            L.append("#%d  %s in %s (a=%s) <<garbled>>:%d" % (i, _addr(rng), fn, _addr(rng), ln))
        if key is not None:
            L.append("key: %s" % key)
        return "\n".join(L) + "\n"
    return _gdb_from_funcs(rng, case, signal, funcs, key)


def _vg(rng, case, op, err, key, no_crypto=False):
    p = "==%d==" % rng.randrange(10000, 99999)
    head = {
        "invalid-read": "Invalid read of size 8",
        "invalid-write": "Invalid write of size 8",
        "use-after-free": "Invalid read of size 8",
        "invalid-free": "Invalid free() / delete / delete[] / realloc()",
        "uninitialized-value": "Conditional jump or move depends on uninitialised value(s)",
    }[err]
    L = ["%s Memcheck, a memory error detector" % p, "%s case: %s" % (p, case), "%s %s" % (p, head)]
    if op and not no_crypto:
        L.append("%s    at %s: %s (vaultseal.c:%d)" % (p, _addr(rng), op, OP_LINE[op]))
    L.append("%s    by %s: seal_record (vaultseal.c:400)" % (p, _addr(rng)))
    if err == "use-after-free":
        L.append("%s  Address %s is 8 bytes inside a block of size 32 free'd" % (p, _addr(rng)))
        L.append("%s    at %s: free (vg_replace_malloc.c:530)" % (p, _addr(rng)))
    if err == "uninitialized-value":
        L.append("%s  Uninitialised value was created by a heap allocation" % p)
    if key is not None:
        L.append("%s  key buffer at %s: %s" % (p, _addr(rng), key))
    return "\n".join(L) + "\n"


def _emit(out, gn, gt, vn, vt):
    if gt is not None:
        open(os.path.join(out, "gdb", gn), "w").write(gt)
    if vt is not None:
        open(os.path.join(out, "valgrind", vn), "w").write(vt)


def make_messy_corpus(seed, n_random=40):
    """Corpus exercising the full grammar, the loose-implementation traps, and
    the two cross-record behaviors (key reuse, non-transitive clustering)."""
    rng = random.Random(seed)
    out = tempfile.mkdtemp(prefix="corpus_messy_")
    os.makedirs(os.path.join(out, "gdb"))
    os.makedirs(os.path.join(out, "valgrind"))
    cid = 1

    def N():
        return "case_%04d" % cid

    k = _valid_key(rng, 32)
    n = N()  # 1: critical, mixed-separator + uppercase key encodings
    _emit(out, n + ".log", _gdb(rng, n, "rsa2048_sign", "SIGSEGV", _enc(rng, 3, k), False),
          n + ".log", _vg(rng, n, "rsa2048_sign", "use-after-free", _enc(rng, 4, k)))
    cid += 1
    n = N()  # 2: padding-mismatched ids
    _emit(out, "case_%d.log" % cid, _gdb(rng, str(cid), "aes256_gcm_open", "SIGSEGV", None, False),
          n + ".log", _vg(rng, n, "aes256_gcm_open", "invalid-read", None))
    cid += 1
    n = N()  # 3: operation conflict
    _emit(out, n + ".log", _gdb(rng, n, "ec_p256_sign", "SIGABRT", None, False),
          n + ".log", _vg(rng, n, "hmac_sha256", "invalid-write", None))
    cid += 1
    n = N()  # 4: gdb-only validated key
    _emit(out, n + ".log", _gdb(rng, n, "hkdf_derive", "SIGSEGV", _enc(rng, 0, _valid_key(rng, 32)), False),
          None, None)
    cid += 1
    n = N()  # 5: valgrind-only
    _emit(out, None, None, n + ".log", _vg(rng, n, "aes256_gcm_seal", "invalid-read", None))
    cid += 1
    n = N()  # 6: malformed gdb -> op from valgrind
    _emit(out, n + ".log", _gdb(rng, n, None, None, None, True),
          n + ".log", _vg(rng, n, "rsa2048_verify", "uninitialized-value", None))
    cid += 1
    n = N()  # 7: decoy hex only -> not leaked, not critical
    _emit(out, n + ".log", _gdb(rng, n, "aes256_gcm_seal", "SIGSEGV", _enc(rng, 0, _decoy(rng, 0)), False),
          n + ".log", _vg(rng, n, "aes256_gcm_seal", "invalid-read", _enc(rng, 1, _decoy(rng, 1))))
    cid += 1
    n = N()  # 8: near-miss op name shadowing the real op (topmost RECOGNIZED wins)
    funcs = [("aes256_gcm_sealer", 99), ("rsa2048_sign", OP_LINE["rsa2048_sign"]), ("seal_record", 407)]
    _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, _enc(rng, 2, _valid_key(rng, 32))),
          n + ".log", _vg(rng, n, "rsa2048_sign", "invalid-read", None))
    cid += 1
    n = N()  # 9: recursion -> identical frames collapse for signature + gdb_frames
    funcs = [("ec_p256_sign", OP_LINE["ec_p256_sign"])] * 3 + [("seal_record", 404), ("main", 512)]
    _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, None),
          n + ".log", _vg(rng, n, "ec_p256_sign", "invalid-write", None))
    cid += 1
    n = N()  # 10: validated (unique) key but no recognized op -> leaked, non-secret, high
    funcs = [("seal_record", 404), ("main", 512)]
    _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, _enc(rng, 1, _valid_key(rng, 24))),
          n + ".log", _vg(rng, n, None, "invalid-read", None, no_crypto=True))
    cid += 1
    n = N()  # 11: all-zero 16-byte key is a valid key (checksum 0x00)
    _emit(out, n + ".log", _gdb(rng, n, "hkdf_derive", "SIGSEGV", _enc(rng, 0, _valid_key(rng, 16, zero=True)), False),
          n + ".log", _vg(rng, n, "hkdf_derive", "invalid-read", None))
    cid += 1
    # 12 & 13: the SAME validated key leaks in two DISTINCT non-secret cases ->
    # shared_key, escalating both from high to critical (cross-record behavior).
    shared = _valid_key(rng, 32)
    n = N()
    _emit(out, n + ".log", _gdb(rng, n, "aes256_gcm_open", "SIGSEGV", _enc(rng, 1, shared), False),
          n + ".log", _vg(rng, n, "aes256_gcm_open", "invalid-read", None))
    cid += 1
    n = N()
    _emit(out, n + ".log", _gdb(rng, n, "hmac_sha256", "SIGABRT", None, False),
          n + ".log", _vg(rng, n, "hmac_sha256", "invalid-write", _enc(rng, 2, shared)))
    cid += 1
    # 14,15,16: non-transitive clustering chain. 14~15 and 15~16 (edit distance 1)
    # but 14 !~ 16 (distance 2); connected components must place all three in one
    # cluster even though no two share an identical signature.
    chain = [
        [("worker_alpha", 210), ("stage_one", 220), ("seal_record", 404), ("main", 512)],
        [("worker_alpha", 210), ("stage_two", 221), ("seal_record", 404), ("main", 512)],
        [("worker_alpha", 210), ("stage_two", 221), ("stage_three", 222), ("main", 512)],
    ]
    for funcs in chain:
        n = N()
        _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, None),
              n + ".log", _vg(rng, n, None, "invalid-read", None, no_crypto=True))
        cid += 1
    # 17 & 18: deletion-variant clustering trap. Their frame sequences share the
    # single-deletion variant [tzmid, seal_record, main] yet are two edits apart,
    # so an index that skips the real edit-distance check would wrongly merge
    # them; connected components must keep them in separate clusters.
    trap = [
        [("tzhead", 205), ("tzmid", 250), ("seal_record", 404), ("main", 512)],
        [("tzmid", 250), ("tztail", 260), ("seal_record", 404), ("main", 512)],
    ]
    for funcs in trap:
        n = N()
        _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, None),
              n + ".log", _vg(rng, n, None, "invalid-read", None, no_crypto=True))
        cid += 1
    # 19: two recognized crypto frames on one stack. Attribution is the TOPMOST
    # recognized frame (aes256_gcm_seal), not the deepest (rsa2048_sign); picking
    # the deepest also flips operation_conflict on. No key, invalid-read.
    n = N()
    funcs = [("aes256_gcm_seal", OP_LINE["aes256_gcm_seal"]),
             ("rsa2048_sign", OP_LINE["rsa2048_sign"]), ("seal_record", 405), ("main", 512)]
    _emit(out, n + ".log", _gdb_from_funcs(rng, n, "SIGSEGV", funcs, None),
          n + ".log", _vg(rng, n, "aes256_gcm_seal", "invalid-read", None))
    cid += 1
    # 20: one case, two DISTINCT validated keys (one in gdb, one in valgrind).
    # The fingerprint is the token of the lexicographically smallest normalized
    # key, not the largest. Non-secret op + unique keys -> high.
    ka, kb = sorted([_valid_key(rng, 32), _valid_key(rng, 32)])
    n = N()
    _emit(out, n + ".log", _gdb(rng, n, "aes256_gcm_open", "SIGSEGV", _enc(rng, 1, ka), False),
          n + ".log", _vg(rng, n, "aes256_gcm_open", "invalid-read", _enc(rng, 2, kb)))
    cid += 1
    # 21: secret op with an uninitialised-value error and no leak/mem error is
    # MEDIUM, not low (a severity row that is easy to drop).
    n = N()
    _emit(out, n + ".log", _gdb(rng, n, "rsa2048_sign", "SIGSEGV", None, False),
          n + ".log", _vg(rng, n, "rsa2048_sign", "uninitialized-value", None))
    cid += 1

    for _ in range(n_random):
        n = N()
        op = rng.choice(ALL_OPS)
        err = rng.choice(ERRS)
        sig = rng.choice(["SIGSEGV", "SIGABRT", "SIGSEGV", None])
        recur = rng.random() < 0.15
        key = None
        r = rng.random()
        if r < 0.4:
            key = _enc(rng, rng.randrange(5), _valid_key(rng, rng.choice([16, 24, 32])))
        elif r < 0.6:
            key = _enc(rng, rng.randrange(2), _decoy(rng, rng.randrange(2)))
        vgkey = key if (key and rng.random() < 0.5) else None
        depth = rng.randrange(1, 4)
        mids = [(rng.choice(HELPERS), 300 + rng.randrange(120)) for _ in range(depth)]
        if recur and mids:
            mids = [mids[0], mids[0]] + mids[1:]
        funcs = ([(op, OP_LINE[op])] if op else []) + mids + [("main", 512)]
        gt = _gdb_from_funcs(rng, n, sig, funcs, key)
        _emit(out, n + ".log", gt, n + ".log", _vg(rng, n, op, err, vgkey))
        cid += 1
    return out


def make_clean_corpus(seed, n=16):
    """Corpus with only public ops and no keys -> only medium/low."""
    rng = random.Random(seed)
    out = tempfile.mkdtemp(prefix="corpus_clean_")
    os.makedirs(os.path.join(out, "gdb"))
    os.makedirs(os.path.join(out, "valgrind"))
    nm = "case_0001"
    _emit(out, nm + ".log", _gdb(rng, nm, "rsa2048_verify", "SIGSEGV", None, False),
          nm + ".log", _vg(rng, nm, "rsa2048_verify", "invalid-read", None))
    for i in range(2, n + 1):
        name = "case_%04d" % i
        op = rng.choice(PUBLIC_OPS)
        err = rng.choice(["invalid-read", "invalid-write", "uninitialized-value"])
        _emit(out, name + ".log", _gdb(rng, name, op, "SIGSEGV", None, False),
              name + ".log", _vg(rng, name, op, err, None))
    return out


def make_scale_corpus(seed, n_cases=PERF_CASES, n_chains=40, n_traps=40):
    """A large corpus with a fully known cluster structure, for the perf test.

    The clustering answer is planted so it can be checked cheaply (no O(n^2)
    reference needed at this size):

    * singletons: signature ``[ua<i>, ub<i>, main]`` with two case-unique frames,
      so every pair is >= 2 edits apart -> each is its own cluster.
    * non-transitive chains: three cases A~B~D (each a single frame edit apart)
      where A and D are two edits apart, so connected components must still merge
      all three -> one cluster per chain, three findings.
    * deletion-variant traps: two cases ``[ga, gm, main]`` and ``[gm, gb, main]``
      that share the single-deletion variant ``[gm, main]`` yet are two edits
      apart -> a candidate that MUST be rejected by the real edit-distance check,
      so the two stay in separate clusters.

    Returns ``(corpus_dir, meta)`` where meta carries the exact expected cluster
    count and the planted case-id groups to assert on. gdb-only (fast to write);
    all findings are low severity, so nothing gates.
    """
    rng = random.Random(seed)
    out = tempfile.mkdtemp(prefix="corpus_scale_")
    os.makedirs(os.path.join(out, "gdb"))
    os.makedirs(os.path.join(out, "valgrind"))
    i = 0

    def emit(funcs):
        nonlocal i
        name = "case_%06d" % i
        cid = "%04d" % i
        _emit(out, name + ".log", _gdb_from_funcs(rng, name, "SIGSEGV", funcs, None), None, None)
        i += 1
        return cid

    n_singletons = n_cases - 3 * n_chains - 2 * n_traps
    assert n_singletons > 0, "n_cases too small for the planted structure"

    chains, traps = [], []
    for c in range(n_chains):
        a = emit([("cx%d" % c, 210), ("c1_%d" % c, 220), ("ctl%d" % c, 230), ("main", 512)])
        b = emit([("cx%d" % c, 210), ("c2_%d" % c, 221), ("ctl%d" % c, 230), ("main", 512)])
        d = emit([("cx%d" % c, 210), ("c2_%d" % c, 221), ("c3_%d" % c, 231), ("main", 512)])
        chains.append((a, b, d))
    for t in range(n_traps):
        g = emit([("ga%d" % t, 240), ("gm%d" % t, 250), ("main", 512)])
        h = emit([("gm%d" % t, 250), ("gb%d" % t, 260), ("main", 512)])
        traps.append((g, h))
    for _ in range(n_singletons):
        emit([("ua%d" % i, 300), ("ub%d" % i, 310), ("main", 512)])

    meta = {
        "n": i,
        "expected_clusters": n_singletons + n_chains + 2 * n_traps,
        "chains": chains,
        "traps": traps,
    }
    return out, meta


# --------------------------------------------------------------------------- #
# Terraform module runner                                                     #
# --------------------------------------------------------------------------- #
def run_module(corpus_dir, gate="high", salt="vaultseal"):
    """Apply the agent's module against a corpus; return (rc, report_or_None, log, raw)."""
    assert os.path.isdir(MODULE_DIR), "%s is missing" % MODULE_DIR
    work = tempfile.mkdtemp(prefix="tfmod_")
    mod = os.path.join(work, "triage")
    shutil.copytree(
        MODULE_DIR, mod,
        ignore=shutil.ignore_patterns(".terraform", ".terraform.lock.hcl",
                                      "terraform.tfstate*", "out", "*.tfstate"),
    )
    out_dir = tempfile.mkdtemp(prefix="tfout_")
    env = dict(os.environ)
    init = subprocess.run(["terraform", "-chdir=" + mod, "init", "-input=false", "-no-color"],
                          capture_output=True, text=True, env=env)
    if init.returncode != 0:
        return init.returncode, None, "INIT FAILED\n" + init.stdout + init.stderr, None
    apply = subprocess.run(
        ["terraform", "-chdir=" + mod, "apply", "-auto-approve", "-input=false", "-no-color",
         "-var", "corpus_dir=" + corpus_dir, "-var", "output_dir=" + out_dir,
         "-var", "severity_gate=" + gate, "-var", "redaction_salt=" + salt],
        capture_output=True, text=True, env=env,
    )
    report = raw = None
    path = os.path.join(out_dir, "triage_report.json")
    if os.path.isfile(path):
        raw = open(path, encoding="utf-8").read()
        try:
            report = json.loads(raw)
        except Exception:
            report = None
    log = "APPLY rc=%d\n%s\n%s" % (apply.returncode, apply.stdout[-2000:], apply.stderr[-2000:])
    return apply.returncode, report, log, raw


def run_module_timed(corpus_dir, gate="high", salt="vaultseal", timeout=PERF_BUDGET_SEC):
    """Like run_module but enforces a hard wall-clock budget on `terraform apply`.

    The apply runs in its own session so a slow (e.g. O(n^2)) analysis can be
    killed as a process group on timeout. Returns a dict with `timed_out`,
    `elapsed` (apply only, not init), `rc`, `report`, and `log`.
    """
    assert os.path.isdir(MODULE_DIR), "%s is missing" % MODULE_DIR
    work = tempfile.mkdtemp(prefix="tfmodperf_")
    mod = os.path.join(work, "triage")
    shutil.copytree(
        MODULE_DIR, mod,
        ignore=shutil.ignore_patterns(".terraform", ".terraform.lock.hcl",
                                      "terraform.tfstate*", "out", "*.tfstate"),
    )
    out_dir = tempfile.mkdtemp(prefix="tfoutperf_")
    env = dict(os.environ)
    init = subprocess.run(["terraform", "-chdir=" + mod, "init", "-input=false", "-no-color"],
                          capture_output=True, text=True, env=env)
    if init.returncode != 0:
        return {"timed_out": False, "elapsed": 0.0, "rc": init.returncode,
                "report": None, "log": "INIT FAILED\n" + init.stdout + init.stderr}
    cmd = ["terraform", "-chdir=" + mod, "apply", "-auto-approve", "-input=false", "-no-color",
           "-var", "corpus_dir=" + corpus_dir, "-var", "output_dir=" + out_dir,
           "-var", "severity_gate=" + gate, "-var", "redaction_salt=" + salt]
    start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, start_new_session=True)
    timed_out = False
    out = err = ""
    rc = None
    try:
        out, err = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            out, err = proc.communicate(timeout=15)
        except Exception:
            pass
    elapsed = time.time() - start
    report = None
    path = os.path.join(out_dir, "triage_report.json")
    if os.path.isfile(path):
        try:
            report = json.loads(open(path, encoding="utf-8").read())
        except Exception:
            report = None
    log = ("timed_out=%s elapsed=%.1fs rc=%s\n%s\n%s"
           % (timed_out, elapsed, rc, (out or "")[-2000:], (err or "")[-2000:]))
    return {"timed_out": timed_out, "elapsed": elapsed, "rc": rc, "report": report, "log": log}


EXACT_FIELDS = ["case_id", "operation", "operation_conflict", "error_class", "crash_signal",
                "key_bits", "leaked", "shared_key", "leaked_key_fingerprint", "severity",
                "correlated", "cluster_id", "gdb_frames"]


@pytest.fixture(scope="module")
def messy():
    corpus = make_messy_corpus(seed=90210, n_random=40)
    rc, report, log, raw = run_module(corpus, gate="high", salt="vaultseal")
    return {"corpus": corpus, "rc": rc, "report": report, "log": log, "raw": raw}


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #
def test_report_is_produced(messy):
    """The module must apply and write a parseable triage_report.json."""
    assert messy["report"] is not None, "no valid report produced:\n" + messy["log"]


def test_top_level_schema_and_counts(messy):
    """Top-level metadata, corpus counts, and severity histogram match the runbook."""
    rep = messy["report"]
    ref = reference_report(messy["corpus"], salt="vaultseal", gate="high")
    for k in ("schema_version", "generated_by", "severity_gate", "gated",
              "max_severity", "severity_counts", "corpus"):
        assert rep.get(k) == ref[k], "top-level field %r mismatch: %r != %r" % (k, rep.get(k), ref[k])


def test_findings_match_reference_exactly(messy):
    """Every finding's classification, correlation, redaction, clustering, and ordering matches reference."""
    rep = messy["report"]
    ref = reference_report(messy["corpus"], salt="vaultseal", gate="high")
    got, exp = rep["findings"], ref["findings"]
    assert len(got) == len(exp), "finding count %d != %d" % (len(got), len(exp))
    assert [f["case_id"] for f in got] == [f["case_id"] for f in exp], "finding ordering differs"
    for g, e in zip(got, exp):
        for field in EXACT_FIELDS:
            assert g.get(field) == e[field], (
                "case %s field %r: %r != %r" % (e["case_id"], field, g.get(field), e[field])
            )


def test_clusters_match_reference_and_are_consistent(messy):
    """The clusters array matches reference and is internally consistent with the findings."""
    rep = messy["report"]
    ref = reference_report(messy["corpus"], salt="vaultseal", gate="high")
    assert rep["clusters"] == ref["clusters"], "clusters array does not match reference"
    assert rep["corpus"]["clusters"] == len(rep["clusters"])
    by_id = {c["cluster_id"]: c for c in rep["clusters"]}
    members = {}
    for f in rep["findings"]:
        assert f["cluster_id"] in by_id, "finding references unknown cluster %s" % f["cluster_id"]
        members.setdefault(f["cluster_id"], []).append(f)
    for cid, c in by_id.items():
        ms = members[cid]
        assert c["size"] == len(ms), "cluster %s size wrong" % cid
        assert c["representative"] == min(m["case_id"] for m in ms), "cluster %s representative wrong" % cid
        assert SEV_RANK[c["severity"]] == max(SEV_RANK[m["severity"]] for m in ms), \
            "cluster %s severity is not the member max" % cid
    keys = [(SEV_RANK[c["severity"]], c["cluster_id"]) for c in rep["clusters"]]
    for a, b in zip(keys, keys[1:]):
        assert a[0] > b[0] or (a[0] == b[0] and a[1] <= b[1]), "clusters not sorted"


def test_clustering_is_connected_components(messy):
    """Cases whose signatures chain by single-frame edits share one cluster even
    though no two of them have an identical signature (group-by-signature is wrong)."""
    rep = messy["report"]
    f = {x["case_id"]: x for x in rep["findings"]}
    c14, c15, c16 = f["0014"]["cluster_id"], f["0015"]["cluster_id"], f["0016"]["cluster_id"]
    assert c14 == c15 == c16, "chain cases not in one cluster: %s %s %s" % (c14, c15, c16)
    # And the members of that cluster do NOT all share one exact signature -> a
    # plain group-by-signature implementation could not have produced it.
    frames_names = {}
    for cid in ("0014", "0015", "0016"):
        frames_names[cid] = tuple(fr.split(" at ", 1)[0] for fr in f[cid]["gdb_frames"][:3])
    assert len(set(frames_names.values())) >= 2, \
        "chain cases unexpectedly share one signature: %r" % frames_names
    # The trap pair 0017/0018 shares a single-deletion variant but is two edits
    # apart, so it must NOT be clustered together: reaching that requires the
    # real edit-distance verification, not just a shared-variant index.
    assert f["0017"]["cluster_id"] != f["0018"]["cluster_id"], (
        "cases 0017/0018 share a deletion variant but are two edits apart; "
        "clustering them together means the edit-distance verify was skipped"
    )


def test_shared_key_reuse_escalates_severity(messy):
    """A validated key that leaks in two distinct cases is shared_key, and escalates
    an otherwise-high non-secret finding to critical (a global, cross-record rule)."""
    rep = messy["report"]
    f = {x["case_id"]: x for x in rep["findings"]}
    for cid in ("0012", "0013"):
        assert f[cid]["leaked"] is True and f[cid]["shared_key"] is True, \
            "case %s should be a shared key leak: %r" % (cid, f[cid])
        assert f[cid]["severity"] == "critical", \
            "shared non-secret key must escalate %s to critical, got %r" % (cid, f[cid]["severity"])
    # A single-case validated key (0010) is not shared and stays high.
    assert f["0010"]["shared_key"] is False and f["0010"]["severity"] == "high"


def test_decoy_hex_not_treated_as_key(messy):
    """Checksum-invalid hex blobs must not mark a case leaked or drive severity to critical."""
    rep = messy["report"]
    f = {x["case_id"]: x for x in rep["findings"]}
    decoy = f["0007"]
    assert decoy["leaked"] is False, "decoy hex was treated as a leaked key"
    assert decoy["leaked_key_fingerprint"] is None
    assert decoy["severity"] != "critical", "decoy case must not be critical"
    for x in rep["findings"]:
        if x["leaked"]:
            assert x["leaked_key_fingerprint"], "leaked case %s missing fingerprint" % x["case_id"]
        else:
            assert x["leaked_key_fingerprint"] is None, "non-leaked case %s has a fingerprint" % x["case_id"]
            assert x["shared_key"] is False, "non-leaked case %s marked shared_key" % x["case_id"]


def test_operation_attribution_is_exact_match(messy):
    """A near-miss function name must not be recognized; the topmost exact crypto frame wins."""
    f = {x["case_id"]: x for x in messy["report"]["findings"]}
    case = f["0008"]
    assert case["operation"] == "rsa2048_sign", "near-miss frame shadowed the real op: %r" % case["operation"]
    assert case["key_bits"] == 2048
    assert case["severity"] == "critical"


def test_recursion_frames_collapse(messy):
    """Immediately-repeated frames collapse before signature and gdb_frames are taken."""
    rep = messy["report"]
    f = {x["case_id"]: x for x in rep["findings"]}
    case = f["0009"]
    names = [fr.split(" at ", 1)[0] for fr in case["gdb_frames"]]
    assert names[:3] == ["ec_p256_sign", "seal_record", "main"], \
        "recursive frames not collapsed in gdb_frames: %r" % names
    for a, b in zip(names, names[1:]):
        assert a != b, "gdb_frames still contains consecutive duplicate frames: %r" % names


def test_validated_key_without_known_operation(messy):
    """A real (unique) key with no recognized operation is leaked, non-secret, and therefore high."""
    f = {x["case_id"]: x for x in messy["report"]["findings"]}
    case = f["0010"]
    assert case["operation"] is None and case["key_bits"] is None
    assert case["leaked"] is True and case["leaked_key_fingerprint"]
    assert case["severity"] == "high"


def test_all_zero_key_is_valid(messy):
    """An all-zero key of a valid length still passes the XOR check and counts as a real key."""
    f = {x["case_id"]: x for x in messy["report"]["findings"]}
    case = f["0011"]
    assert case["leaked"] is True, "all-zero valid-length key was not recognized"
    assert case["severity"] == "critical"


def test_operation_uses_topmost_crypto_frame(messy):
    """With two recognized crypto frames on the stack, attribution is the topmost
    one; taking the deepest also spuriously trips operation_conflict."""
    f = {x["case_id"]: x for x in messy["report"]["findings"]}
    case = f["0019"]
    assert case["operation"] == "aes256_gcm_seal", \
        "operation must be the topmost recognized crypto frame, got %r" % case["operation"]
    assert case["key_bits"] == 256
    assert case["operation_conflict"] is False, "gdb and valgrind agree; no conflict expected"


def test_fingerprint_is_smallest_key(messy):
    """When a case carries two distinct validated keys, the fingerprint is the
    token of the lexicographically smallest normalized key."""
    rep = messy["report"]
    ref = {x["case_id"]: x for x in reference_report(messy["corpus"], salt="vaultseal", gate="high")["findings"]}
    f = {x["case_id"]: x for x in rep["findings"]}
    case = f["0020"]
    assert case["leaked"] is True and case["leaked_key_fingerprint"]
    assert case["leaked_key_fingerprint"] == ref["0020"]["leaked_key_fingerprint"], \
        "fingerprint must be the smallest key's token (reference), got %r" % case["leaked_key_fingerprint"]
    assert case["severity"] == "high"


def test_secret_uninitialized_value_is_medium(messy):
    """A secret-bearing op with an uninitialised-value error (no leak, no memory
    error) is medium severity, not low."""
    f = {x["case_id"]: x for x in messy["report"]["findings"]}
    case = f["0021"]
    assert case["operation"] == "rsa2048_sign" and case["leaked"] is False
    assert case["error_class"] == "uninitialized-value"
    assert case["severity"] == "medium", \
        "secret op + uninitialised value must be medium, got %r" % case["severity"]


def test_fix_is_in_analyze_logic_not_a_shortcut():
    """The regressions must be fixed in analyze.py's own logic. Delegating to the
    reference oracle (or any external process) is not a valid solution."""
    src = open(os.path.join(MODULE_DIR, "scripts", "analyze.py"), encoding="utf-8").read().lower()
    # Ban the mechanisms an implementation could use to shell out to /app/oracle
    # (or any external helper). The word "oracle" itself is allowed — it appears
    # in the module docstring — so this keys on delegation primitives, not prose.
    banned = ["subprocess", "os.system", "os.popen", ".popen(", "os.exec", "os.spawn",
              "os.fork", "check_output", "check_call", "ctypes", "getoutput", "runpy"]
    hits = [b for b in banned if b in src]
    assert not hits, (
        "analyze.py must reproduce the behavior in its own logic, not by invoking "
        "the reference oracle or shelling out to an external process: found %r" % hits
    )


def test_ordering_is_severity_then_case_id(messy):
    """Findings are sorted by descending severity then ascending case id."""
    keys = [(SEV_RANK[f["severity"]], f["case_id"]) for f in messy["report"]["findings"]]
    for a, b in zip(keys, keys[1:]):
        assert a[0] > b[0] or (a[0] == b[0] and a[1] <= b[1]), "bad ordering at %r -> %r" % (a, b)


def test_no_raw_key_material_leaks(messy):
    """No raw key hex may survive into the report (redaction completeness)."""
    raw = messy["raw"]
    assert raw is not None
    assert re.search(r"[0-9a-fA-F]{32}", raw) is None, "found 32+ contiguous hex chars (raw key?)"
    assert KEY_RE.search(raw) is None, "found a key-length hex run in the report"
    assert "vsk1:" in raw, "expected redacted fingerprints in a corpus that contains real keys"


def test_leak_context_present_and_redacted(messy):
    """leak_context is null exactly when a case is not leaked, and never raw."""
    for f in messy["report"]["findings"]:
        if f["leaked"]:
            assert f.get("leak_context"), "leaked case %s missing leak_context" % f["case_id"]
            assert KEY_RE.search(f["leak_context"]) is None, "leak_context not redacted"
        else:
            assert f.get("leak_context") is None, "non-leaked case %s has leak_context" % f["case_id"]


def test_gate_trips_on_critical_corpus(messy):
    """A corpus with a critical finding must fail `terraform apply` (non-zero)."""
    assert messy["report"]["gated"] is True
    assert messy["rc"] != 0, "gated corpus must fail apply, got rc=0:\n" + messy["log"]


def test_determinism_byte_for_byte():
    """Applying the module twice on the same corpus yields identical bytes."""
    corpus = make_messy_corpus(seed=4242, n_random=25)
    _, _, _, raw1 = run_module(corpus, gate="high", salt="vaultseal")
    _, _, _, raw2 = run_module(corpus, gate="high", salt="vaultseal")
    assert raw1 is not None and raw2 is not None
    assert raw1 == raw2, "report is not deterministic across runs"


def test_salt_changes_fingerprints_not_structure():
    """Changing the salt changes key fingerprints but not classification, clustering, or structure."""
    corpus = make_messy_corpus(seed=7, n_random=25)
    _, rep_a, log_a, _ = run_module(corpus, gate="high", salt="vaultseal")
    _, rep_b, log_b, _ = run_module(corpus, gate="high", salt="PEPPER-2")
    assert rep_a and rep_b, "reports missing:\n%s\n%s" % (log_a, log_b)
    fa = {f["case_id"]: f for f in rep_a["findings"]}
    fb = {f["case_id"]: f for f in rep_b["findings"]}
    ref_b = {f["case_id"]: f for f in reference_report(corpus, salt="PEPPER-2", gate="high")["findings"]}
    changed = False
    for cid, a in fa.items():
        b = fb[cid]
        assert a["severity"] == b["severity"], "salt changed severity for %s" % cid
        assert a["cluster_id"] == b["cluster_id"], "salt changed cluster_id for %s" % cid
        assert a["shared_key"] == b["shared_key"], "salt changed shared_key for %s" % cid
        assert a["leaked"] == b["leaked"]
        if a["leaked"]:
            assert a["leaked_key_fingerprint"] != b["leaked_key_fingerprint"], \
                "fingerprint for %s did not change with salt" % cid
            assert b["leaked_key_fingerprint"] == ref_b[cid]["leaked_key_fingerprint"], \
                "salted fingerprint for %s does not match reference" % cid
            changed = True
    assert changed, "test corpus had no real keys to salt"


def test_gate_not_tripped_on_clean_corpus():
    """A corpus with only medium/low findings passes the default (high) gate."""
    corpus = make_clean_corpus(seed=55)
    rc, rep, log, raw = run_module(corpus, gate="high", salt="vaultseal")
    assert rep is not None, "no report:\n" + log
    assert rep["max_severity"] in ("medium", "low"), "clean corpus should not reach high"
    assert rep["gated"] is False
    assert rc == 0, "non-gated apply must succeed, got rc=%d:\n%s" % (rc, log)


def test_gate_threshold_is_configurable():
    """Lowering the gate to 'medium' makes the same clean corpus gate and fail."""
    corpus = make_clean_corpus(seed=56)
    rc, rep, log, raw = run_module(corpus, gate="medium", salt="vaultseal")
    assert rep is not None, "no report:\n" + log
    assert rep["severity_counts"]["medium"] >= 1
    assert rep["gated"] is True
    assert rc != 0, "medium-gated corpus must fail apply:\n" + log


def test_matches_reference_on_clean_corpus():
    """Full reference equality (findings + clusters) on a corpus with no keys and only public ops."""
    corpus = make_clean_corpus(seed=57)
    _, rep, log, _ = run_module(corpus, gate="high", salt="vaultseal")
    assert rep is not None, "no report:\n" + log
    ref = reference_report(corpus, salt="vaultseal", gate="high")
    assert [f["case_id"] for f in rep["findings"]] == [f["case_id"] for f in ref["findings"]]
    for g, e in zip(rep["findings"], ref["findings"]):
        for field in EXACT_FIELDS:
            assert g.get(field) == e[field], "clean case %s field %r mismatch" % (e["case_id"], field)
    assert rep["clusters"] == ref["clusters"], "clean clusters mismatch"


def test_scales_to_large_corpus():
    """On a corpus of tens of thousands of cases the analysis must finish within
    the time budget AND still compute clustering as exact connected components.

    A naive all-pairs O(n^2) edit-distance scan does not finish in time and fails
    the budget; an implementation that indexes candidates but skips the real
    edit-distance verification wrongly merges the deletion-variant trap pairs and
    fails the cluster-count / trap assertions. Only a correct near-linear
    connected-components implementation passes both."""
    corpus, meta = make_scale_corpus(seed=1234)
    res = run_module_timed(corpus, gate="high", salt="vaultseal", timeout=PERF_BUDGET_SEC)
    assert not res["timed_out"], (
        "analysis did not finish within %ds on %d cases — an all-pairs O(n^2) "
        "clustering does not scale (see runbook 'Performance and scale')\n%s"
        % (PERF_BUDGET_SEC, meta["n"], res["log"])
    )
    rep = res["report"]
    assert rep is not None, "no report produced on the large corpus:\n" + res["log"]
    assert res["elapsed"] < PERF_BUDGET_SEC, "over budget: %.1fs" % res["elapsed"]
    assert rep["corpus"]["total_findings"] == meta["n"], (
        "finding count %d != %d" % (rep["corpus"]["total_findings"], meta["n"])
    )
    assert rep["corpus"]["clusters"] == meta["expected_clusters"], (
        "cluster count %d != expected %d — clustering at scale is not the exact "
        "connected-components grouping" % (rep["corpus"]["clusters"], meta["expected_clusters"])
    )
    f = {x["case_id"]: x for x in rep["findings"]}
    for tri in meta["chains"]:
        ids = {f[c]["cluster_id"] for c in tri}
        assert len(ids) == 1, "non-transitive chain %r split across clusters %r at scale" % (tri, ids)
    for a, b in meta["traps"]:
        assert f[a]["cluster_id"] != f[b]["cluster_id"], (
            "cases %s/%s share a single-deletion variant but are two edits apart; "
            "they must not be clustered together (missing edit-distance verification)" % (a, b)
        )
