#!/usr/bin/env python3
"""vaultseal triage reference oracle.

This is the authoritative reference implementation of the vaultseal crash-triage
pipeline. It reads a corpus directory (the same ``gdb/`` + ``valgrind/`` layout
the Terraform module consumes) and prints the canonical ``triage_report.json``
for that corpus to stdout. Given the same corpus, salt, and gate it always
prints byte-for-byte identical output.

It is shipped as an opaque binary: run it on any corpus you like and treat its
output as ground truth, but you cannot read its source. Use it to determine what
the triage pipeline is *supposed* to produce, then make the module in
``/app/triage`` reproduce it.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

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


def norm_hex(s):
    s = s.strip()
    if s[:2].lower() == "0x":
        s = s[2:]
    return re.sub(r"[ \t:]", "", s).lower()


def is_validated_key(h):
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


def fingerprint(salt, h):
    return "vsk1:" + hashlib.sha256((salt + ":" + h).encode("utf-8")).hexdigest()[:8]


def nonkey_token(h):
    return "vsx1:" + hashlib.sha256(("nonkey:" + h).encode("utf-8")).hexdigest()[:8]


def redact_text(text, salt):
    def repl(m):
        h = norm_hex(m.group(0))
        return fingerprint(salt, h) if is_validated_key(h) else nonkey_token(h)
    return KEY_RE.sub(repl, text)


def canon_id(raw, stem):
    for src in (raw, stem):
        if not src:
            continue
        m = re.search(r"(\d+)", src)
        if m:
            return "%04d" % int(m.group(1))
    base = re.sub(r"[^A-Za-z0-9]+", "_", (raw or stem or "unknown").strip()).strip("_")
    return base or "unknown"


def collapse_frames(frames):
    out = []
    for f in frames:
        if not out or out[-1] != f:
            out.append(f)
    return out


def edit_distance(a, b):
    la, lb = len(a), len(b)
    if a == b:
        return 0
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def connected_clusters(sig_by_case):
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

    by_sig = {}
    for c in ids:
        by_sig.setdefault(tuple(sig_by_case[c]), []).append(c)
    reps = []
    for key, members in by_sig.items():
        for m in members[1:]:
            union(members[0], m)
        reps.append((key, members[0]))

    buckets = {}
    for key, rep in reps:
        variants = [key] + [key[:i] + key[i + 1:] for i in range(len(key))]
        for v in variants:
            buckets.setdefault(v, []).append((key, rep))

    for members in buckets.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            ka, ra = members[i]
            for j in range(i + 1, len(members)):
                kb, rb = members[j]
                if find(ra) == find(rb):
                    continue
                if edit_distance(list(ka), list(kb)) <= 1:
                    union(ra, rb)
    return {c: find(c) for c in ids}


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_gdb(text):
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
    frames = collapse_frames(frames)
    op = next((f.split(" at ", 1)[0] for f in frames if f.split(" at ", 1)[0] in CRYPTO_OPS), None)
    return {"raw_case": raw_case, "signal": signal, "frames": frames, "op": op, "text": text}


def parse_valgrind(text):
    raw_case = None
    for line in text.splitlines():
        m = re.search(r"case:\s*(\S+)", line)
        if m and raw_case is None:
            raw_case = m.group(1).strip()
    low = text.lower()
    freed = ("free'd" in low) or ("freed" in low)
    has_read = "invalid read" in low
    has_write = "invalid write" in low
    if (has_read or has_write) and freed:
        error_class = "use-after-free"
    elif "invalid free" in low or "mismatched free" in low:
        error_class = "invalid-free"
    elif has_read:
        error_class = "invalid-read"
    elif has_write:
        error_class = "invalid-write"
    elif "uninitialised" in low or "uninitialized" in low:
        error_class = "uninitialized-value"
    else:
        error_class = "unknown"
    op = next((m.group(1) for m in VG_FRAME_RE.finditer(text) if m.group(1) in CRYPTO_OPS), None)
    return {"raw_case": raw_case, "error_class": error_class, "op": op, "text": text}


def classify(secret, error_class, leaked, shared):
    if leaked and secret:
        return "critical"
    if leaked and (not secret) and shared:
        return "critical"
    if leaked and not secret:
        return "high"
    if secret and error_class in MEM_ERR:
        return "high"
    if (not secret) and error_class in MEM_ERR:
        return "medium"
    if secret and error_class == "uninitialized-value":
        return "medium"
    return "low"


def build_report(corpus_dir, salt="vaultseal", gate="high"):
    gdb = {}
    for path in sorted(glob.glob(os.path.join(corpus_dir, "gdb", "*"))):
        if not os.path.isfile(path):
            continue
        try:
            data = parse_gdb(_read(path))
        except Exception:
            data = {"raw_case": None, "signal": None, "frames": [], "op": None, "text": ""}
        gdb[canon_id(data["raw_case"], os.path.splitext(os.path.basename(path))[0])] = data
    valg = {}
    for path in sorted(glob.glob(os.path.join(corpus_dir, "valgrind", "*"))):
        if not os.path.isfile(path):
            continue
        try:
            data = parse_valgrind(_read(path))
        except Exception:
            data = {"raw_case": None, "error_class": "unknown", "op": None, "text": ""}
        valg[canon_id(data["raw_case"], os.path.splitext(os.path.basename(path))[0])] = data

    case_ids = set(gdb) | set(valg)

    case_keys = {}
    key_cases = {}
    for cid in case_ids:
        g, v = gdb.get(cid), valg.get(cid)
        combined = ((g["text"] if g else "") + "\n" + (v["text"] if v else ""))
        keys = sorted({norm_hex(m) for m in KEY_RE.findall(combined)
                       if is_validated_key(norm_hex(m))})
        case_keys[cid] = keys
        for k in keys:
            key_cases.setdefault(k, set()).add(cid)

    sig_by_case = {}
    for cid in case_ids:
        g = gdb.get(cid)
        sig_by_case[cid] = ([f.split(" at ", 1)[0] for f in g["frames"]]
                            if (g and g["frames"]) else ["<unknown>"])
    root_of = connected_clusters(sig_by_case)

    findings = []
    for cid in case_ids:
        g = gdb.get(cid)
        v = valg.get(cid)
        op_g = g["op"] if g else None
        op_v = v["op"] if v else None
        operation = op_g or op_v
        error_class = v["error_class"] if v else "unknown"
        keys = case_keys[cid]
        leaked = bool(keys)
        shared = any(len(key_cases[k]) >= 2 for k in keys)
        leak_context = None
        if leaked:
            combined = ((g["text"] if g else "") + "\n" + (v["text"] if v else ""))
            for line in combined.splitlines():
                if any(is_validated_key(norm_hex(m)) for m in KEY_RE.findall(line)):
                    leak_context = redact_text(line.strip(), salt)
                    break
        secret = CRYPTO_OPS.get(operation, {}).get("secret", False)
        severity = classify(secret, error_class, leaked, shared)
        frames = g["frames"] if g else []
        findings.append({
            "case_id": cid,
            "operation": operation,
            "operation_conflict": bool(op_g and op_v and op_g != op_v),
            "error_class": error_class,
            "crash_signal": g["signal"] if g else None,
            "key_bits": CRYPTO_OPS[operation]["key_bits"] if operation in CRYPTO_OPS else None,
            "leaked": leaked,
            "shared_key": bool(leaked and shared),
            "leaked_key_fingerprint": fingerprint(salt, keys[0]) if leaked else None,
            "leak_context": leak_context,
            "severity": severity,
            "correlated": bool(g and v),
            "cluster_root": root_of[cid],
            "gdb_frames": [redact_text(f, salt) for f in frames[:6]],
        })

    members = {}
    for f in findings:
        members.setdefault(f["cluster_root"], []).append(f)
    cluster_by_root = {}
    for root, ms in members.items():
        member_ids = sorted(m["case_id"] for m in ms)
        cid_hash = "clu:" + hashlib.sha256("|".join(member_ids).encode("utf-8")).hexdigest()[:8]
        rep = member_ids[0]
        rep_sig = sig_by_case[rep][:3]
        cluster_by_root[root] = {
            "cluster_id": cid_hash,
            "signature": rep_sig,
            "size": len(ms),
            "severity": RANK_SEV[max(SEV_RANK[m["severity"]] for m in ms)],
            "representative": rep,
        }

    for f in findings:
        f["cluster_id"] = cluster_by_root[f.pop("cluster_root")]["cluster_id"]

    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], f["case_id"]))
    clusters = list(cluster_by_root.values())
    clusters.sort(key=lambda c: (-SEV_RANK[c["severity"]], c["cluster_id"]))

    counts = {s: 0 for s in SEV_RANK}
    for f in findings:
        counts[f["severity"]] += 1
    max_rank = max((SEV_RANK[f["severity"]] for f in findings), default=None)
    gate_rank = SEV_RANK.get(gate, SEV_RANK["high"])
    gated = max_rank is not None and max_rank >= gate_rank
    report = {
        "schema_version": "1.0",
        "generated_by": "vaultseal-triage",
        "severity_gate": gate,
        "gated": gated,
        "max_severity": RANK_SEV[max_rank] if max_rank is not None else None,
        "severity_counts": counts,
        "corpus": {
            "gdb_cases": len(gdb),
            "valgrind_cases": len(valg),
            "correlated": len(set(gdb) & set(valg)),
            "clusters": len(clusters),
            "total_findings": len(findings),
        },
        "clusters": clusters,
        "findings": findings,
    }
    return report, gated


def dumps(report):
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="vaultseal triage reference oracle")
    ap.add_argument("--corpus-dir", required=True)
    ap.add_argument("--severity-gate", default="high")
    ap.add_argument("--redaction-salt", default="vaultseal")
    args = ap.parse_args(argv)
    report, _gated = build_report(args.corpus_dir, args.redaction_salt, args.severity_gate)
    sys.stdout.write(dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
