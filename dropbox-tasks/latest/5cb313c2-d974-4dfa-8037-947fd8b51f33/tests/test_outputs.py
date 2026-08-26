from __future__ import annotations

import hashlib
import json
import os
import random
import re
import subprocess
from pathlib import Path

import pytest


def solve(text: str):
    keys = {}
    images = []
    attest = []
    policies = []
    members = {}
    delegates = []
    requests = []
    revokes = []
    roots = []
    bundles = []
    checkpoints = []
    witnesses = []
    witness_reqs = []
    root_pins = []
    compromises = []
    splitviews = []
    binds = []
    embargoes = []
    key_scopes = []
    chains = []
    holds = []
    uniques = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if p[0] == "KEY":
            keys[p[1]] = {"issuer": p[2], "subject": p[3], "not_before": int(p[4]), "not_after": int(p[5]), "trusted": p[6] == "1"}
        elif p[0] == "IMAGE":
            images.append({"name": p[1], "digest": p[2], "env": p[3], "tier": p[4]})
        elif p[0] == "ATTEST":
            attest.append({"name": p[1], "digest": p[2], "predicate": p[3], "builder": p[4], "key": p[5], "timestamp": int(p[6]), "log_index": int(p[7]), "source_digest": p[8], "order": len(attest)})
        elif p[0] == "LOGROOT":
            roots.append({"log_id": p[1], "root_hash": p[2], "not_before": int(p[3]), "not_after": int(p[4]), "trusted": p[5] == "1"})
        elif p[0] == "BUNDLE":
            bundles.append({"log_index": int(p[1]), "log_id": p[2], "integrated_time": int(p[3]), "tree_size": int(p[4]), "root_hash": p[5]})
        elif p[0] == "CHECKPOINT":
            checkpoints.append({"log_id": p[1], "tree_size": int(p[2]), "root_hash": p[3], "prev_root_hash": p[4], "prev_tree_size": int(p[5]), "trusted": p[6] == "1"})
        elif p[0] == "WITNESS":
            witnesses.append({"log_id": p[1], "tree_size": int(p[2]), "root_hash": p[3], "key": p[4], "timestamp": int(p[5]), "source_digest": p[6], "trusted": p[7] == "1"})
        elif p[0] == "WITNESSREQ":
            witness_reqs.append({"log_id": p[1], "root_prefix": p[2], "min_count": int(p[3]), "distinct": p[4] == "distinct-key", "max_age": int(p[5]), "source_prefix": p[6] if len(p) > 6 else "*"})
        elif p[0] == "ROOTPIN":
            root_pins.append({"env": p[1], "tier": p[2], "log_id": p[3], "root_prefix": p[4], "not_before": int(p[5]), "not_after": int(p[6]), "trusted": p[7] == "1"})
        elif p[0] == "SPLITVIEW":
            splitviews.append({"log_id": p[1], "tree_size": int(p[2]), "root_hash": p[3], "trusted": p[4] == "1"})
        elif p[0] == "BIND":
            binds.append({"builder": p[1], "issuer": p[2], "subject_prefix": p[3], "source_prefix": p[4], "env": p[5], "tier": p[6], "not_before": int(p[7]), "not_after": int(p[8]), "trusted": p[9] == "1"})
        elif p[0] == "EMBARGO":
            embargoes.append({"env": p[1], "tier": p[2], "builder": p[3], "source_prefix": p[4], "start": int(p[5]), "end": int(p[6])})
        elif p[0] == "KEYSCOPE":
            key_scopes.append({"key": p[1], "env": p[2], "tier": p[3], "builder": p[4], "source_prefix": p[5], "not_before": int(p[6]), "not_after": int(p[7]), "trusted": p[8] == "1"})
        elif p[0] == "HOLD":
            holds.append({"env": p[1], "tier": p[2], "builder": p[3], "source_prefix": p[4], "marker_predicate": p[5], "marker_builder": p[6], "marker_issuer": p[7], "marker_source_prefix": p[8], "start": int(p[9]), "end": int(p[10])})
        elif p[0] == "CHAIN":
            chains.append({"env": p[1], "tier": p[2], "predicate": p[3], "builder": p[4], "prev_predicate": p[5], "prev_builder": p[6], "max_delta": int(p[7]), "source_prefix": p[8]})
        elif p[0] == "UNIQUE":
            uniques.append({"env": p[1], "tier": p[2]})
        elif p[0] == "REQUIRE":
            policies.append(("require", {"env": p[1], "tier": p[2], "predicate": p[3], "builder": p[4], "issuer": p[5], "max_age": int(p[6]), "min_log": int(p[7]), "hard": p[8] == "hard", "subject_prefix": p[9] if len(p) > 9 else "*", "source_prefix": p[10] if len(p) > 10 else "*"}))
        elif p[0] == "QUORUM":
            policies.append(("quorum", {"env": p[1], "tier": p[2], "label": p[3], "min_count": int(p[4]), "distinct": p[5] == "distinct-key", "hard": p[6] == "hard", "min_source_groups": int(p[7]) if len(p) > 7 else 0}))
        elif p[0] == "MEMBER":
            members.setdefault(p[1], []).append({"predicate": p[2], "builder": p[3], "issuer": p[4], "max_age": int(p[5]), "min_log": int(p[6]), "source_prefix": p[7], "subject_prefix": p[8] if len(p) > 8 else "*"})
        elif p[0] == "DELEGATE":
            delegates.append({"parent": p[1], "child": p[2], "not_before": int(p[3]), "not_after": int(p[4]), "subject_prefix": p[5], "source_prefix": p[6]})
        elif p[0] == "REQUEST":
            requests.append((p[1], p[2], int(p[3])))
        elif p[0] == "REVOKE":
            if len(p) == 2:
                revokes.append((p[1], None, None))
            else:
                revokes.append((p[1], int(p[2]), int(p[3])))
        elif p[0] == "COMPROMISE":
            compromises.append((p[1], int(p[2]), int(p[3]), p[4]))

    def revoked(key, timestamp):
        for rkey, start, end in revokes:
            if rkey != key:
                continue
            if start is None or start <= timestamp <= end:
                return True
        return False

    def compromised(key, timestamp, source_digest):
        for ckey, start, end, prefix in compromises:
            if ckey == key and start <= timestamp <= end and (prefix == "*" or source_digest.startswith(prefix)):
                return True
        return False

    def transparent(a, env, tier):
        candidates = [b for b in bundles if b["log_index"] == a["log_index"]]
        if not candidates:
            return True
        for b in candidates:
            if b["integrated_time"] != a["timestamp"] or b["tree_size"] <= a["log_index"]:
                continue
            if any(s["log_id"] == b["log_id"] and s["tree_size"] == b["tree_size"] and s["root_hash"] == b["root_hash"] and s["trusted"] for s in splitviews):
                continue
            for r in roots:
                if (
                    r["log_id"] == b["log_id"]
                    and r["root_hash"] == b["root_hash"]
                    and r["trusted"]
                    and r["not_before"] <= b["integrated_time"] <= r["not_after"]
                    and checkpoint_ok(b)
                    and root_pin_ok(b, env, tier)
                    and witness_ok(b)
                ):
                    return True
        return False

    def checkpoint_ok(bundle):
        matching = [
            c
            for c in checkpoints
            if c["log_id"] == bundle["log_id"]
            and c["tree_size"] == bundle["tree_size"]
            and c["root_hash"] == bundle["root_hash"]
        ]
        if not matching:
            return True
        for c in matching:
            if not c["trusted"] or c["prev_tree_size"] >= bundle["tree_size"]:
                continue
            if c["prev_tree_size"] == 0:
                return True
            if any(
                r["log_id"] == bundle["log_id"]
                and r["root_hash"] == c["prev_root_hash"]
                and r["trusted"]
                and r["not_after"] <= bundle["integrated_time"]
                for r in roots
            ):
                return True
        return False

    def root_pin_ok(bundle, env, tier):
        matching = [
            p
            for p in root_pins
            if wildcard_match(p["env"], env)
            and wildcard_match(p["tier"], tier)
            and wildcard_match(p["log_id"], bundle["log_id"])
        ]
        if not matching:
            return True
        return any(
            p["trusted"]
            and p["not_before"] <= bundle["integrated_time"] <= p["not_after"]
            and wildcard_match(p["root_prefix"], bundle["root_hash"], True)
            for p in matching
        )

    def witness_ok(bundle):
        matching = [
            r
            for r in witness_reqs
            if r["log_id"] == bundle["log_id"]
            and (r["root_prefix"] == "*" or bundle["root_hash"].startswith(r["root_prefix"]))
        ]
        if not matching:
            return True
        for req in matching:
            count = 0
            used_keys = set()
            for w in witnesses:
                if (
                    w["log_id"] != bundle["log_id"]
                    or w["tree_size"] != bundle["tree_size"]
                    or w["root_hash"] != bundle["root_hash"]
                    or not w["trusted"]
                    or w["timestamp"] > bundle["integrated_time"]
                    or bundle["integrated_time"] - w["timestamp"] > req["max_age"]
                    or (req["source_prefix"] != "*" and not w["source_digest"].startswith(req["source_prefix"]))
                ):
                    continue
                if req["distinct"] and w["key"] in used_keys:
                    continue
                k = keys.get(w["key"])
                if (
                    not k
                    or not (k["not_before"] <= w["timestamp"] <= k["not_after"])
                    or revoked(w["key"], w["timestamp"])
                    or compromised(w["key"], w["timestamp"], w["source_digest"])
                    or not trusted_for(w["key"], w["timestamp"], w["source_digest"], set())
                ):
                    continue
                if req["distinct"]:
                    used_keys.add(w["key"])
                count += 1
                if count >= req["min_count"]:
                    break
            if count < req["min_count"]:
                return False
        return True

    def wildcard_match(rule_value, actual, prefix=False):
        if rule_value == "*":
            return True
        return actual.startswith(rule_value) if prefix else rule_value == actual

    def bind_ok(a, key, env, tier):
        relevant = [b for b in binds if b["builder"] == a["builder"]]
        if not relevant:
            return True
        for b in relevant:
            if (
                b["trusted"]
                and b["not_before"] <= a["timestamp"] <= b["not_after"]
                and wildcard_match(b["issuer"], key["issuer"])
                and wildcard_match(b["subject_prefix"], key["subject"], True)
                and wildcard_match(b["source_prefix"], a["source_digest"], True)
                and wildcard_match(b["env"], env)
                and wildcard_match(b["tier"], tier)
            ):
                return True
        return False

    def embargoed(a, now, env, tier):
        for e in embargoes:
            if (
                wildcard_match(e["env"], env)
                and wildcard_match(e["tier"], tier)
                and wildcard_match(e["builder"], a["builder"])
                and wildcard_match(e["source_prefix"], a["source_digest"], True)
                and (e["start"] <= now <= e["end"] or e["start"] <= a["timestamp"] <= e["end"])
            ):
                return True
        return False

    def key_scope_ok(a, env, tier):
        relevant = [s for s in key_scopes if s["key"] == a["key"]]
        if not relevant:
            return True
        for s in relevant:
            if (
                s["trusted"]
                and s["not_before"] <= a["timestamp"] <= s["not_after"]
                and wildcard_match(s["env"], env)
                and wildcard_match(s["tier"], tier)
                and wildcard_match(s["builder"], a["builder"])
                and wildcard_match(s["source_prefix"], a["source_digest"], True)
            ):
                return True
        return False

    def marker_valid(marker, issuer, source_prefix, env, tier):
        if source_prefix != "*" and not marker["source_digest"].startswith(source_prefix):
            return False
        if not transparent(marker, env, tier):
            return False
        k = keys.get(marker["key"])
        if not k or k["issuer"] != issuer:
            return False
        if revoked(marker["key"], marker["timestamp"]) or compromised(marker["key"], marker["timestamp"], marker["source_digest"]):
            return False
        if not (k["not_before"] <= marker["timestamp"] <= k["not_after"]):
            return False
        if not bind_ok(marker, k, env, tier):
            return False
        if not key_scope_ok(marker, env, tier):
            return False
        return trusted_for(marker["key"], marker["timestamp"], marker["source_digest"], set())

    def held(a, now, env, tier):
        for h in holds:
            if not (
                wildcard_match(h["env"], env)
                and wildcard_match(h["tier"], tier)
                and wildcard_match(h["builder"], a["builder"])
                and wildcard_match(h["source_prefix"], a["source_digest"], True)
                and (h["start"] <= now <= h["end"] or h["start"] <= a["timestamp"] <= h["end"])
            ):
                continue
            for marker in attest:
                if marker["name"] != a["name"] or marker["digest"] != a["digest"]:
                    continue
                if marker["predicate"] != h["marker_predicate"] or marker["builder"] != h["marker_builder"]:
                    continue
                if marker_valid(marker, h["marker_issuer"], h["marker_source_prefix"], env, tier):
                    return True
        return False

    def base_valid(a, r, now, env, tier):
        if a["predicate"] != r["predicate"] or a["builder"] != r["builder"] or a["log_index"] < r["min_log"] or now - a["timestamp"] > r["max_age"]:
            return False
        if embargoed(a, now, env, tier):
            return False
        if held(a, now, env, tier):
            return False
        if not transparent(a, env, tier):
            return False
        prefix = r.get("source_prefix")
        if prefix not in (None, "*") and not a["source_digest"].startswith(prefix):
            return False
        k = keys.get(a["key"])
        if not k or not k["trusted"] or revoked(a["key"], a["timestamp"]) or compromised(a["key"], a["timestamp"], a["source_digest"]) or k["issuer"] != r["issuer"] or not (k["not_before"] <= a["timestamp"] <= k["not_after"]):
            if not k or revoked(a["key"], a["timestamp"]) or compromised(a["key"], a["timestamp"], a["source_digest"]) or k["issuer"] != r["issuer"] or not (k["not_before"] <= a["timestamp"] <= k["not_after"]):
                return False
        if not bind_ok(a, k, env, tier):
            return False
        if not key_scope_ok(a, env, tier):
            return False
        if not trusted_for(a["key"], a["timestamp"], a["source_digest"], set()):
            return False
        subject_prefix = r.get("subject_prefix", "*")
        return subject_prefix == "*" or k["subject"].startswith(subject_prefix)

    def chain_ok(a, now, env, tier):
        for c in chains:
            if not (
                wildcard_match(c["env"], env)
                and wildcard_match(c["tier"], tier)
                and c["predicate"] == a["predicate"]
                and c["builder"] == a["builder"]
                and wildcard_match(c["source_prefix"], a["source_digest"], True)
            ):
                continue
            req = {
                "predicate": c["prev_predicate"],
                "builder": c["prev_builder"],
                "issuer": keys.get(a["key"], {}).get("issuer", ""),
                "max_age": 10**18,
                "min_log": -10**18,
                "source_prefix": "*",
                "subject_prefix": "*",
            }
            found = False
            for prev in attest:
                if prev["name"] != a["name"] or prev["digest"] != a["digest"]:
                    continue
                if prev["timestamp"] > a["timestamp"] or a["timestamp"] - prev["timestamp"] > c["max_delta"]:
                    continue
                if prev["log_index"] >= a["log_index"]:
                    continue
                if base_valid(prev, req, now, env, tier):
                    found = True
                    break
            if not found:
                return False
        return True

    def valid(a, r, now, env, tier):
        return base_valid(a, r, now, env, tier) and chain_ok(a, now, env, tier)

    def trusted_for(key, timestamp, source_digest, seen):
        if key in seen:
            return False
        k = keys.get(key)
        if not k or revoked(key, timestamp) or compromised(key, timestamp, source_digest) or not (k["not_before"] <= timestamp <= k["not_after"]):
            return False
        if k["trusted"]:
            return True
        seen = seen | {key}
        for d in delegates:
            if d["child"] != key or not (d["not_before"] <= timestamp <= d["not_after"]):
                continue
            if d["source_prefix"] != "*" and not source_digest.startswith(d["source_prefix"]):
                continue
            if d["subject_prefix"] != "*" and not k["subject"].startswith(d["subject_prefix"]):
                continue
            if trusted_for(d["parent"], timestamp, source_digest, seen):
                return True
        return False

    def best_attestation(name, digest, r, now, env, tier, used_orders=None):
        cands = [
            a for a in attest
            if a["name"] == name
            and a["digest"] == digest
            and (used_orders is None or a["order"] not in used_orders)
            and valid(a, r, now, env, tier)
        ]
        cands.sort(key=lambda a: (-a["timestamp"], -a["log_index"], a["order"]))
        return cands[0] if cands else None

    def source_group(a):
        return a["source_digest"].split("/", 1)[0]

    def select_quorum(name, digest, q, now, env, tier, used_orders=None):
        group = members.get(q["label"], [])
        candidate_lists = []
        for m in group:
            cands = [
                a for a in attest
                if a["name"] == name
                and a["digest"] == digest
                and (used_orders is None or a["order"] not in used_orders)
                and valid(a, m, now, env, tier)
            ]
            cands.sort(key=lambda a: (-a["timestamp"], -a["log_index"], a["order"]))
            candidate_lists.append(cands)
        best = None
        best_score = None

        def score(selected):
            flat = [sum(1 for item in selected if item is not None)]
            flat.append(len({source_group(item) for item in selected if item is not None}))
            for item in selected:
                if item is None:
                    flat.extend([0, 0, 0, 0])
                else:
                    flat.extend([1, item["timestamp"], item["log_index"], -item["order"]])
            return tuple(flat)

        def dfs(idx, used_keys, used_records, selected):
            nonlocal best, best_score
            if idx == len(candidate_lists):
                if sum(1 for item in selected if item is not None) < q["min_count"]:
                    return
                if len({source_group(item) for item in selected if item is not None}) < q["min_source_groups"]:
                    return
                sc = score(selected)
                if best_score is None or sc > best_score:
                    best_score = sc
                    best = selected[:]
                return
            selected.append(None)
            dfs(idx + 1, used_keys, used_records, selected)
            selected.pop()
            for cand in candidate_lists[idx]:
                if q["distinct"] and cand["key"] in used_keys:
                    continue
                if used_orders is not None and cand["order"] in used_records:
                    continue
                selected.append(cand)
                if q["distinct"]:
                    used_keys.add(cand["key"])
                if used_orders is not None:
                    used_records.add(cand["order"])
                dfs(idx + 1, used_keys, used_records, selected)
                if used_orders is not None:
                    used_records.remove(cand["order"])
                if q["distinct"]:
                    used_keys.remove(cand["key"])
                selected.pop()

        dfs(0, set(), set(used_orders or set()), [])
        if best is None:
            return None
        return [(m, a) for m, a in zip(group, best) if a is not None]

    decisions = []
    evidence = []
    approved = denied = warnings = 0
    for name, digest, now in requests:
        rid = f"{name}@{digest}"
        img = next((i for i in images if i["name"] == name and i["digest"] == digest), None)
        if img is None:
            decisions.append({"request": rid, "status": "denied", "reasons": ["image-missing"], "warnings": []})
            denied += 1
            continue
        used_orders = set() if any(u["env"] == img["env"] and u["tier"] == img["tier"] for u in uniques) else None
        reasons = []
        warns = []
        for kind, policy in policies:
            if policy["env"] != img["env"] or policy["tier"] != img["tier"]:
                continue
            if kind == "require":
                a = best_attestation(name, digest, policy, now, img["env"], img["tier"], used_orders)
                if not a:
                    if policy["hard"]:
                        reasons.append(f"missing:{policy['predicate']}:{policy['builder']}")
                    else:
                        warns.append(f"missing:{policy['predicate']}:{policy['builder']}")
                        warnings += 1
                    continue
                evidence.append({"request": rid, "predicate": policy["predicate"], "builder": policy["builder"], "key": a["key"], "timestamp": a["timestamp"], "log_index": a["log_index"], "source_digest": a["source_digest"]})
                if used_orders is not None:
                    used_orders.add(a["order"])
            else:
                selected = select_quorum(name, digest, policy, now, img["env"], img["tier"], used_orders)
                if selected is None:
                    msg = f"missing:quorum:{policy['label']}"
                    if policy["hard"]:
                        reasons.append(msg)
                    else:
                        warns.append(msg)
                        warnings += 1
                    continue
                for member, a in selected:
                    evidence.append({"request": rid, "predicate": member["predicate"], "builder": member["builder"], "key": a["key"], "timestamp": a["timestamp"], "log_index": a["log_index"], "source_digest": a["source_digest"]})
                    if used_orders is not None:
                        used_orders.add(a["order"])
        if reasons:
            denied += 1
            status = "denied"
        else:
            approved += 1
            status = "approved"
        decisions.append({"request": rid, "status": status, "reasons": reasons, "warnings": warns})
    return {"decisions": decisions, "evidence": evidence, "summary": {"requests": len(requests), "approved": approved, "denied": denied, "warnings": warnings}}

APP = Path("/app/task_file")
SRC = APP / "src" / "main.rs"
PUBLIC = APP / "input" / "release.txt"
PUBLIC_TEXT = """KEY fulcio-prod fulcio@example.com ci@example.com 100 10000 1
KEY old fulcio@example.com ci@example.com 1 500 1
KEY untrusted fulcio@example.com ci@example.com 1 10000 0
IMAGE api sha256aaa prod critical
IMAGE worker sha256bbb prod standard
ATTEST api sha256aaa slsa-build github fulcio-prod 900 50 srcA
ATTEST api sha256aaa vuln-scan trivy fulcio-prod 910 53 srcA
ATTEST worker sha256bbb slsa-build github old 450 10 srcB
ATTEST worker sha256bbb slsa-build github fulcio-prod 920 65 srcB
REQUIRE prod critical slsa-build github fulcio@example.com 200 40 hard
REQUIRE prod critical vuln-scan trivy fulcio@example.com 200 40 warn
REQUIRE prod standard slsa-build github fulcio@example.com 200 40 hard
REQUEST api sha256aaa 1000
REQUEST worker sha256bbb 1000
"""
PUBLIC_SHA256 = hashlib.sha256(PUBLIC_TEXT.encode()).hexdigest()


def run_auditor(src: Path, release: str, tmp_path: Path):
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    cache_dir = Path(os.environ.get("AUDITOR_BINARY_CACHE", "/tmp/auditor-binary-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = cache_dir / f"auditor-{digest}"
    if not binary.exists():
        tmp_binary = tmp_path / f"auditor-{digest}"
        subprocess.run(["rustc", str(src), "-O", "-o", str(tmp_binary)], check=True, cwd=tmp_path)
        tmp_binary.replace(binary)
    inp = tmp_path / "release.txt"
    out = tmp_path / "report.json"
    inp.write_text(release)
    subprocess.run([str(binary), str(inp), str(out)], check=True, cwd=tmp_path)
    return json.loads(out.read_text()), out.read_text()


def assert_matches(release: str, tmp_path: Path):
    actual, raw = run_auditor(SRC, release, tmp_path)
    assert raw.endswith("\n")
    assert actual == solve(release)
    assert list(actual) == ["decisions", "evidence", "summary"]
    assert list(actual["summary"]) == ["requests", "approved", "denied", "warnings"]


def test_public_input_is_unchanged():
    """The bundled release policy input is fixed and must not be edited."""
    assert PUBLIC.read_text() == PUBLIC_TEXT
    assert hashlib.sha256(PUBLIC.read_bytes()).hexdigest() == PUBLIC_SHA256


def test_placeholder_source_is_rejected():
    """The committed placeholder empty report cannot pass behavioral tests."""
    text = SRC.read_text()
    assert "approved\\\":0" not in text
    assert "decisions\\\":[],\\\"evidence\\\":[]" not in text


def test_single_rust_source_without_verifier_access():
    """The submitted Rust source must be self-contained and cannot read verifier or solution files."""
    rust_files = sorted((APP / "src").rglob("*.rs"))
    assert rust_files == [SRC]
    text = SRC.read_text()
    for pat in [r"/tests", r"/solution", r"/logs", r"reward\.txt", r"ctrf\.json", r"include_str!\s*\(", r"include_bytes!\s*\(", r"Command::new"]:
        assert not re.search(pat, text)


def test_public_report_matches_reference(tmp_path):
    """The public case includes hard and warn requirements, stale old evidence, and two approvals."""
    assert_matches(PUBLIC_TEXT, tmp_path)


def test_revoked_and_untrusted_keys_do_not_satisfy_hard_requirement(tmp_path):
    """Revoked and untrusted keys are ignored even if their attestation otherwise matches."""
    graph = """
KEY good fulcio ci 1 1000 1
KEY bad fulcio ci 1 1000 1
KEY noisy fulcio ci 1 1000 0
IMAGE api d1 prod critical
ATTEST api d1 slsa github bad 900 99 src
ATTEST api d1 slsa github noisy 950 100 src
REQUIRE prod critical slsa github fulcio 200 50 hard
REQUEST api d1 1000
REVOKE bad
"""
    assert_matches(graph, tmp_path)


def test_evidence_tiebreak_timestamp_log_then_record_order(tmp_path):
    """Evidence selection uses newest timestamp, then highest log index, then earliest attestation record."""
    graph = """
KEY k fulcio ci 1 2000 1
IMAGE app d2 prod critical
ATTEST app d2 slsa github k 900 50 src-old
ATTEST app d2 slsa github k 950 40 src-newer-lowlog
ATTEST app d2 slsa github k 950 80 src-best
ATTEST app d2 slsa github k 950 80 src-late-same
REQUIRE prod critical slsa github fulcio 200 10 hard
REQUEST app d2 1000
"""
    assert_matches(graph, tmp_path)


def test_warn_missing_approves_but_counts_warning(tmp_path):
    """A missing warn requirement does not deny the release but appears in decision warnings and summary count."""
    graph = """
KEY k fulcio ci 1 2000 1
IMAGE ui d3 prod standard
ATTEST ui d3 slsa github k 900 70 src
REQUIRE prod standard slsa github fulcio 200 50 hard
REQUIRE prod standard vuln trivy fulcio 200 50 warn
REQUEST ui d3 1000
"""
    assert_matches(graph, tmp_path)


def test_wrong_issuer_validity_age_and_log_boundaries(tmp_path):
    """Issuer, key validity, max age, and minimum log constraints are all enforced together."""
    graph = """
KEY early fulcio ci 1 500 1
KEY other otherca ci 1 2000 1
KEY good fulcio ci 1 2000 1
IMAGE svc d4 prod critical
ATTEST svc d4 slsa github early 700 100 src-invalid-key-window
ATTEST svc d4 slsa github other 900 100 src-wrong-issuer
ATTEST svc d4 slsa github good 700 100 src-too-old
ATTEST svc d4 slsa github good 940 20 src-low-log
REQUIRE prod critical slsa github fulcio 200 50 hard
REQUEST svc d4 1000
"""
    assert_matches(graph, tmp_path)


def test_image_missing_and_policy_scope_by_env_tier(tmp_path):
    """Requests for missing images are denied and requirements apply only to matching env/tier."""
    graph = """
KEY k fulcio ci 1 2000 1
IMAGE api d5 staging critical
ATTEST api d5 slsa github k 900 60 src
REQUIRE prod critical vuln trivy fulcio 200 50 hard
REQUIRE staging critical slsa github fulcio 200 50 hard
REQUEST api d5 1000
REQUEST api missing 1000
"""
    assert_matches(graph, tmp_path)


@pytest.mark.parametrize("seed", [6101, 6102, 6103, 6104])
def test_generated_policy_matrices(seed: int, tmp_path):
    """Generated matrices combine key trust, revocation, age, log, warn requirements, and request ordering."""
    rng = random.Random(seed)
    lines = []
    for i in range(5):
        lines.append(f"KEY k{i} {'fulcio' if i % 2 == 0 else 'other'} ci {rng.randint(1, 200)} {rng.randint(800, 1800)} {1 if i != 3 else 0}")
    envs = ["prod", "staging"]
    tiers = ["critical", "standard"]
    for i in range(8):
        lines.append(f"IMAGE img{i} d{i} {envs[i % 2]} {tiers[(i // 2) % 2]}")
        for pred, builder in [("slsa", "github"), ("scan", "trivy")]:
            key = f"k{rng.randrange(5)}"
            lines.append(f"ATTEST img{i} d{i} {pred} {builder} {key} {rng.randint(300, 1200)} {rng.randint(1, 100)} src{i}{pred}")
    lines.extend([
        "REQUIRE prod critical slsa github fulcio 600 20 hard",
        "REQUIRE prod critical scan trivy fulcio 600 20 warn",
        "REQUIRE staging standard slsa github fulcio 500 10 hard",
        "REQUIRE staging critical scan trivy fulcio 500 10 warn",
    ])
    for i in rng.sample(range(8), 5):
        lines.append(f"REQUEST img{i} d{i} {rng.randint(900, 1300)}")
    for i in rng.sample(range(5), 2):
        lines.append(f"REVOKE k{i}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_dense_release_train(tmp_path):
    """A dense hand case stresses multiple request scopes and deterministic evidence order."""
    graph = """
KEY kA fulcio ci 1 5000 1
KEY kB fulcio ci 1 5000 1
KEY kC other ci 1 5000 1
IMAGE api da prod critical
IMAGE batch db prod critical
IMAGE ui dc staging standard
ATTEST api da slsa github kA 1000 80 src-api-build
ATTEST api da scan trivy kB 990 70 src-api-scan
ATTEST batch db slsa github kC 1000 90 src-wrong
ATTEST batch db slsa github kA 900 40 src-low
ATTEST ui dc slsa github kB 1000 55 src-ui-build
ATTEST ui dc scan trivy kB 1001 56 src-ui-scan
REQUIRE prod critical slsa github fulcio 150 50 hard
REQUIRE prod critical scan trivy fulcio 150 50 warn
REQUIRE staging standard slsa github fulcio 100 50 hard
REQUIRE staging standard scan trivy fulcio 100 50 warn
REQUEST api da 1050
REQUEST batch db 1050
REQUEST ui dc 1050
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_duplicate_requirements_emit_duplicate_evidence(tmp_path):
    """Duplicate matching requirements are evaluated independently and emit duplicate evidence entries."""
    graph = """
KEY k fulcio ci 1 3000 1
IMAGE api ddup prod critical
ATTEST api ddup slsa github k 1000 60 src-build
REQUIRE prod critical slsa github fulcio 100 50 hard
REQUIRE prod critical slsa github fulcio 100 50 hard
REQUEST api ddup 1050
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_future_attestation_negative_age_is_allowed_by_formula(tmp_path):
    """The age check is exactly now - timestamp <= max_age, so future timestamps can satisfy policy."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dfuture prod critical
ATTEST api dfuture slsa github k 1200 60 src-future
REQUIRE prod critical slsa github fulcio 10 50 hard
REQUEST api dfuture 1000
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_revoked_best_falls_back_to_older_valid_evidence(tmp_path):
    """If the newest matching attestation uses a revoked key, the selector falls back to older valid evidence."""
    graph = """
KEY old fulcio ci 1 5000 1
KEY new fulcio ci 1 5000 1
IMAGE api dfallback prod critical
ATTEST api dfallback slsa github old 900 70 src-old-valid
ATTEST api dfallback slsa github new 1000 90 src-new-revoked
REQUIRE prod critical slsa github fulcio 200 50 hard
REQUEST api dfallback 1050
REVOKE new
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_same_image_requested_at_different_times_changes_decision(tmp_path):
    """Two requests for the same image can diverge because max_age is evaluated with each request's now."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dtime prod critical
ATTEST api dtime slsa github k 1000 70 src
REQUIRE prod critical slsa github fulcio 100 50 hard
REQUEST api dtime 1050
REQUEST api dtime 1201
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_validity_boundary_is_inclusive(tmp_path):
    """Key validity accepts attestations exactly at not_before and not_after boundaries."""
    graph = """
KEY edge fulcio ci 1000 1000 1
IMAGE edge dvalid prod standard
ATTEST edge dvalid slsa github edge 1000 55 src-edge
REQUIRE prod standard slsa github fulcio 100 50 hard
REQUEST edge dvalid 1000
"""
    assert_matches(graph, tmp_path)


def test_brutal_hard_hold_marker_invalidates_newer_matching_evidence_only(tmp_path):
    """A valid hold marker blocks matching release evidence and forces fallback to older safe evidence."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dhold prod critical
ATTEST api dhold slsa github rel 1200 90 src/prod/new-held
ATTEST api dhold slsa github rel 900 70 src/prod/old-safe
ATTEST api dhold hold incident sec 1100 80 alerts/prod/active
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 600 50 hard * src/prod/
REQUEST api dhold 1400
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/old-safe"


def test_brutal_hard_hold_marker_must_be_trusted_and_transparency_valid(tmp_path):
    """Untrusted or transparency-invalid hold markers do not activate an incident hold."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY badsec security ir 1 5000 0
KEY goodsec security ir 1 5000 1
IMAGE api dholdtrust prod critical
ATTEST api dholdtrust slsa github rel 1200 120 src/prod/new-valid
ATTEST api dholdtrust hold incident badsec 1190 119 alerts/prod/untrusted
ATTEST api dholdtrust hold incident goodsec 1180 118 alerts/prod/bad-bundle
LOGROOT rekor root 1000 1300 1
BUNDLE 118 rekor 1180 118 root
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dholdtrust 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/new-valid"


def test_brutal_hard_hold_request_time_boundary_denies_even_old_attestation(tmp_path):
    """A hold applies when request time is inside the hold window even if evidence predates it."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdnow prod standard
ATTEST api dholdnow slsa github rel 900 90 src/release/a
ATTEST api dholdnow hold incident sec 950 91 alerts/release/h
HOLD prod standard github src/release/ hold incident security alerts/release/ 1000 1100
REQUIRE prod standard slsa github fulcio 500 50 hard * src/release/
REQUEST api dholdnow 1050
REQUEST api dholdnow 1200
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [d["status"] for d in actual["decisions"]] == ["denied", "approved"]


def test_brutal_hard_hold_quorum_reoptimizes_distinct_keys_after_trigger(tmp_path):
    """Quorum selection must filter held candidates before maximizing member count and distinct keys."""
    graph = """
KEY buildA fulcio repo:build 1 5000 1
KEY buildB fulcio repo:build 1 5000 1
KEY scanA fulcio repo:scan 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdq prod critical
ATTEST api dholdq build github buildA 1300 130 src/build/held
ATTEST api dholdq build github buildB 1200 120 src/build/safe
ATTEST api dholdq scan trivy scanA 1210 121 src/scan/safe
ATTEST api dholdq hold incident sec 1250 122 alerts/prod/q
HOLD prod critical github src/build/ hold incident security alerts/prod/ 1240 1400
QUORUM prod critical release 2 distinct-key hard
MEMBER release build github fulcio 500 50 src/build repo:build
MEMBER release scan trivy fulcio 500 50 src/scan repo:scan
REQUEST api dholdq 1450
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["buildB", "scanA"]


def test_brutal_hard_hold_blocks_chain_predecessor_but_not_release_attestation(tmp_path):
    """Hold filtering also applies to CHAIN predecessors, forcing a denial when provenance is held."""
    graph = """
KEY build fulcio repo:build 1 5000 1
KEY scan fulcio repo:scan 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdchain prod critical
ATTEST api dholdchain source-check fetch build 1000 70 src/base/held
ATTEST api dholdchain slsa github build 1200 90 src/release/final
ATTEST api dholdchain hold incident sec 1100 80 alerts/prod/chain
HOLD prod critical fetch src/base/ hold incident security alerts/prod/ 950 1150
CHAIN prod critical slsa github source-check fetch 500 src/release/
REQUIRE prod critical slsa github fulcio 500 50 hard repo:build src/release/
REQUEST api dholdchain 1300
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "denied"
    assert actual["decisions"][0]["reasons"] == ["missing:slsa:github"]
    assert actual["evidence"] == []


def test_brutal_hard_hold_marker_delegation_and_revocation_are_global(tmp_path):
    """A hold marker can be delegated, but revoked delegation parents prevent activation."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY root security root 1 5000 1
KEY marker security ir/delegated 1 5000 0
IMAGE api dholddeleg prod critical
ATTEST api dholddeleg slsa github rel 1200 90 src/prod/new
ATTEST api dholddeleg hold incident marker 1100 80 alerts/prod/delegated
DELEGATE root marker 1000 1300 ir/ alerts/prod/
REVOKE root 1050 1150
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dholddeleg 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/new"


def test_brutal_hard_hold_marker_builder_binding_is_required_when_present(tmp_path):
    """Hold marker attestations must pass builder binding just like release evidence."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir/prod 1 5000 1
IMAGE api dholdbind prod critical
ATTEST api dholdbind slsa github rel 1200 90 src/prod/new
ATTEST api dholdbind hold incident sec 1100 80 alerts/prod/marker
BIND incident security ir/staging alerts/prod/ prod critical 1000 1300 1
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dholdbind 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/new"


def test_brutal_hard_hold_marker_splitview_and_checkpoint_filter_activation(tmp_path):
    """Only a transparency-valid marker activates the hold; split-viewed marker roots are ignored."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdtlog prod critical
ATTEST api dholdtlog slsa github rel 1200 90 src/prod/new-held
ATTEST api dholdtlog slsa github rel 900 70 src/prod/old-safe
ATTEST api dholdtlog hold incident sec 1100 300 alerts/prod/split
ATTEST api dholdtlog hold incident sec 1110 310 alerts/prod/good
LOGROOT rekor prev 500 1000 1
LOGROOT rekor badroot 1000 1300 1
LOGROOT rekor goodroot 1000 1300 1
BUNDLE 300 rekor 1100 301 badroot
BUNDLE 310 rekor 1110 311 goodroot
CHECKPOINT rekor 301 badroot prev 200 1
CHECKPOINT rekor 311 goodroot prev 200 1
SPLITVIEW rekor 301 badroot 1
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 600 50 hard * src/prod/
REQUEST api dholdtlog 1400
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/old-safe"


def test_brutal_hard_hold_marker_not_evidence_and_duplicate_holds_are_additive(tmp_path):
    """Hold marker rows never emit evidence, while duplicate holds can independently block candidates."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholddup prod critical
ATTEST api dholddup slsa github rel 1300 130 src/a/held-by-first
ATTEST api dholddup scan trivy rel 1290 129 src/b/held-by-second
ATTEST api dholddup sbom syft rel 1100 100 src/c/good
ATTEST api dholddup hold incident sec 1200 120 alerts/prod/marker
HOLD prod critical github src/a/ hold incident security alerts/prod/ 1250 1400
HOLD prod critical trivy src/b/ hold incident security alerts/prod/ 1250 1400
REQUIRE prod critical slsa github fulcio 500 50 warn * src/a/
REQUIRE prod critical scan trivy fulcio 500 50 warn * src/b/
REQUIRE prod critical sbom syft fulcio 500 50 hard * src/c/
REQUEST api dholddup 1450
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["decisions"][0]["warnings"] == ["missing:slsa:github", "missing:scan:trivy"]
    assert [e["predicate"] for e in actual["evidence"]] == ["sbom"]


def test_brutal_hard_hold_embargo_chain_quorum_supermesh(tmp_path):
    """Hold, embargo, chain, split-view, and quorum filters compose before global evidence selection."""
    graph = """
KEY buildA fulcio repo:build 1 5000 1
KEY buildB fulcio repo:build 1 5000 1
KEY scanA fulcio repo:scan 1 5000 1
KEY scanB fulcio repo:scan 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdsuper prod critical
ATTEST api dholdsuper source-check fetch buildA 1000 100 base/good
ATTEST api dholdsuper build github buildA 1320 320 build/held
ATTEST api dholdsuper build github buildB 1260 260 build/safe
ATTEST api dholdsuper scan trivy scanA 1310 310 scan/embargoed
ATTEST api dholdsuper scan trivy scanB 1240 240 scan/safe
ATTEST api dholdsuper hold incident sec 1210 210 alerts/prod/super
LOGROOT rekor prev 500 1000 1
LOGROOT rekor bad 1000 1400 1
LOGROOT rekor good 1000 1400 1
BUNDLE 320 rekor 1320 321 bad
BUNDLE 260 rekor 1260 261 good
BUNDLE 310 rekor 1310 311 good
BUNDLE 240 rekor 1240 241 good
BUNDLE 210 rekor 1210 211 good
CHECKPOINT rekor 321 bad prev 200 1
CHECKPOINT rekor 261 good prev 200 1
CHECKPOINT rekor 311 good prev 200 1
CHECKPOINT rekor 241 good prev 200 1
CHECKPOINT rekor 211 good prev 200 1
SPLITVIEW rekor 321 bad 1
HOLD prod critical github build/ hold incident security alerts/prod/ 1300 1400
EMBARGO prod critical trivy scan/embargoed 1300 1350
CHAIN prod critical build github source-check fetch 400 build/
QUORUM prod critical release 2 distinct-key hard 2
MEMBER release build github fulcio 500 50 build/ repo:build
MEMBER release scan trivy fulcio 500 50 scan/ repo:scan
REQUEST api dholdsuper 1450
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["buildB", "scanB"]
    assert [e["source_digest"].split("/", 1)[0] for e in actual["evidence"]] == ["build", "scan"]


def test_brutal_hard_hold_marker_is_case_local_and_image_exact(tmp_path):
    """Hold markers for another digest or image name must not activate against the requested release."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dtarget prod critical
IMAGE api dother prod critical
IMAGE other dtarget prod critical
ATTEST api dtarget slsa github rel 1200 90 src/prod/target
ATTEST api dother hold incident sec 1100 80 alerts/prod/wrong-digest
ATTEST other dtarget hold incident sec 1110 81 alerts/prod/wrong-name
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dtarget 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/target"


def test_brutal_hard_hold_wildcards_are_secure_but_only_in_documented_fields(tmp_path):
    """Hold wildcards apply to documented hold fields while marker issuer remains exact."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY wrong other-security ir 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dwild prod critical
ATTEST api dwild slsa github rel 1220 92 source/release/new
ATTEST api dwild slsa github rel 900 70 source/release/old
ATTEST api dwild hold incident wrong 1100 80 alerts/any/wrong-issuer
ATTEST api dwild hold incident sec 1110 81 alerts/any/right-issuer
HOLD * * * source/ hold incident security * 1000 1300
REQUIRE prod critical slsa github fulcio 600 50 hard * source/
REQUEST api dwild 1400
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "source/release/old"


def test_brutal_hard_hold_candidate_cannot_self_activate_without_marker_predicate(tmp_path):
    """Release evidence cannot activate its own hold unless it also matches the marker predicate and builder."""
    graph = """
KEY rel fulcio ci 1 5000 1
IMAGE api dself prod critical
ATTEST api dself slsa github rel 1200 90 src/prod/release
HOLD prod critical github src/prod/ hold incident fulcio src/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dself 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert len(actual["evidence"]) == 1


def test_brutal_hard_hold_marker_compromise_source_scope_blocks_activation(tmp_path):
    """Compromise source scope applies to hold marker keys and can prevent hold activation."""
    graph = """
KEY rel fulcio ci 1 5000 1
KEY sec security ir 1 5000 1
IMAGE api dholdcomp prod critical
ATTEST api dholdcomp slsa github rel 1200 90 src/prod/new
ATTEST api dholdcomp hold incident sec 1100 80 alerts/prod/marker
COMPROMISE sec 1000 1200 alerts/prod/
HOLD prod critical github src/prod/ hold incident security alerts/prod/ 1000 1300
REQUIRE prod critical slsa github fulcio 500 50 hard * src/prod/
REQUEST api dholdcomp 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/new"


@pytest.mark.parametrize("seed", [13101, 13102, 13103])
def test_brutal_hard_generated_hold_incident_response_mesh(seed: int, tmp_path):
    """Generated hold meshes combine marker trust, source scoping, request time, and fallback evidence."""
    rng = random.Random(seed)
    newer = 1200 + rng.randrange(20)
    older = 900 + rng.randrange(50)
    hold_start = 1100
    hold_end = 1300
    source = rng.choice(["src/prod/", "src/release/"])
    alert = rng.choice(["alerts/prod/", "alerts/release/"])
    marker_trust = rng.choice([0, 1])
    lines = [
        "KEY rel fulcio ci 1 5000 1",
        f"KEY sec security ir 1 5000 {marker_trust}",
        "IMAGE api dholdgen prod critical",
        f"ATTEST api dholdgen slsa github rel {newer} 90 {source}new",
        f"ATTEST api dholdgen slsa github rel {older} 70 {source}old",
        f"ATTEST api dholdgen hold incident sec {hold_start + 5} 80 {alert}marker",
        f"HOLD prod critical github {source} hold incident security {alert} {hold_start} {hold_end}",
        f"REQUIRE prod critical slsa github fulcio 500 50 hard * {source}",
        "REQUEST api dholdgen 1250",
    ]
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [14101, 14102, 14103, 14104])
def test_brutal_hard_generated_hold_quorum_chain_attack_lattice(seed: int, tmp_path):
    """Generated lattices force global filtering before chain and quorum evidence optimization."""
    rng = random.Random(seed)
    hold_start = 1200 + rng.randrange(20)
    hold_end = hold_start + 120
    request_now = hold_end + 50
    build_held_ts = hold_start + rng.randrange(20)
    build_safe_ts = hold_start - 40 - rng.randrange(20)
    scan_bad_ts = hold_start + 10 + rng.randrange(15)
    scan_safe_ts = hold_start - 50 - rng.randrange(20)
    marker_ts = hold_start + 5
    lines = [
        "KEY buildA fulcio repo:build 1 5000 1",
        "KEY buildB fulcio repo:build 1 5000 1",
        "KEY scanA fulcio repo:scan 1 5000 1",
        "KEY scanB fulcio repo:scan 1 5000 1",
        "KEY sec security ir 1 5000 1",
        "IMAGE api dholdlat prod critical",
        "ATTEST api dholdlat source-check fetch buildA 1000 100 base/provenance",
        f"ATTEST api dholdlat build github buildA {build_held_ts} 420 build/held-{seed}",
        f"ATTEST api dholdlat build github buildB {build_safe_ts} 320 build/safe-{seed}",
        f"ATTEST api dholdlat scan trivy scanA {scan_bad_ts} 410 scan/embargo-{seed}",
        f"ATTEST api dholdlat scan trivy scanB {scan_safe_ts} 310 scan/safe-{seed}",
        f"ATTEST api dholdlat hold incident sec {marker_ts} 300 alerts/prod/marker-{seed}",
        "LOGROOT rekor prev 500 1000 1",
        "LOGROOT rekor root 1000 5000 1",
        f"BUNDLE 420 rekor {build_held_ts} 421 root",
        f"BUNDLE 320 rekor {build_safe_ts} 321 root",
        f"BUNDLE 410 rekor {scan_bad_ts} 411 root",
        f"BUNDLE 310 rekor {scan_safe_ts} 311 root",
        f"BUNDLE 300 rekor {marker_ts} 301 root",
        "CHECKPOINT rekor 421 root prev 200 1",
        "CHECKPOINT rekor 321 root prev 200 1",
        "CHECKPOINT rekor 411 root prev 200 1",
        "CHECKPOINT rekor 311 root prev 200 1",
        "CHECKPOINT rekor 301 root prev 200 1",
        f"HOLD prod critical github build/ hold incident security alerts/prod/ {hold_start} {hold_end}",
        f"EMBARGO prod critical trivy scan/embargo- {hold_start} {hold_end}",
        "CHAIN prod critical build github source-check fetch 500 build/",
        "QUORUM prod critical release 2 distinct-key hard 2",
        "MEMBER release build github fulcio 800 50 build/ repo:build",
        "MEMBER release scan trivy fulcio 800 50 scan/ repo:scan",
        f"REQUEST api dholdlat {request_now}",
    ]
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_scoped_revocation_falls_back_by_attestation_timestamp(tmp_path):
    """A scoped revoke invalidates only attestations whose timestamp is inside the inclusive revoke window."""
    graph = """
KEY old fulcio ci 1 5000 1
KEY scoped fulcio ci 1 5000 1
KEY fresh fulcio ci 1 5000 1
IMAGE api dscope prod critical
ATTEST api dscope slsa github old 700 60 src-old
ATTEST api dscope slsa github scoped 950 90 src-revoked-window
ATTEST api dscope slsa github fresh 980 40 src-low-log
REQUIRE prod critical slsa github fulcio 400 50 hard
REQUEST api dscope 1000
REVOKE scoped 900 960
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["key"] == "old"


def test_brutal_hard_distinct_key_quorum_requires_global_selection_not_greedy_best(tmp_path):
    """The quorum selector must choose a lower-ranked member candidate when it enables a larger distinct-key set."""
    graph = """
KEY k1 fulcio ci 1 5000 1
KEY k2 fulcio ci 1 5000 1
IMAGE api dquorum prod critical
ATTEST api dquorum build github k1 1000 90 src/build-best
ATTEST api dquorum build github k2 990 95 src/build-alt
ATTEST api dquorum scan trivy k1 995 85 src/scan-only
QUORUM prod critical release-gate 2 distinct-key hard
MEMBER release-gate build github fulcio 200 50 src/
MEMBER release-gate scan trivy fulcio 200 50 src/
REQUEST api dquorum 1050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["k2", "k1"]
    assert [e["predicate"] for e in actual["evidence"]] == ["build", "scan"]


def test_brutal_hard_quorum_warning_source_prefix_and_policy_order(tmp_path):
    """Warn quorums use source prefixes, emit no partial evidence on failure, and preserve surrounding policy order."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dqwarn prod standard
ATTEST api dqwarn slsa github k 1000 90 src/main/build
ATTEST api dqwarn sbom syft k 1001 91 other/sbom
REQUIRE prod standard slsa github fulcio 200 50 hard
QUORUM prod standard provenance 2 same-key-ok warn
MEMBER provenance slsa github fulcio 200 50 src/main/
MEMBER provenance sbom syft fulcio 200 50 src/main/
REQUEST api dqwarn 1050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["decisions"][0]["warnings"] == ["missing:quorum:provenance"]
    assert len(actual["evidence"]) == 1
    assert actual["summary"]["warnings"] == 1


def test_brutal_hard_direct_requirement_uses_key_subject_and_source_prefix(tmp_path):
    """Extended REQUIRE fields constrain both the signing key subject and attestation source digest."""
    graph = """
KEY wrong-sub fulcio repo:other/service 1 5000 1
KEY wrong-src fulcio repo:team/service 1 5000 1
KEY good fulcio repo:team/service-release 1 5000 1
IMAGE api dsubject prod critical
ATTEST api dsubject slsa github wrong-sub 1100 90 src/release/build-a
ATTEST api dsubject slsa github wrong-src 1110 95 other/build-b
ATTEST api dsubject slsa github good 1000 70 src/release/build-c
REQUIRE prod critical slsa github fulcio 300 50 hard repo:team/ src/release/
REQUEST api dsubject 1200
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["key"] == "good"


def test_brutal_hard_quorum_member_subject_prefix_blocks_shared_key_shortcut(tmp_path):
    """Quorum members can require different key subject namespaces even when same-key reuse is allowed."""
    graph = """
KEY build-key fulcio repo:team/build 1 5000 1
KEY scan-key fulcio repo:team/security 1 5000 1
KEY tempting fulcio repo:team/build 1 5000 1
IMAGE api dqsubject prod critical
ATTEST api dqsubject build github build-key 1000 90 src/build/main
ATTEST api dqsubject scan trivy tempting 1010 99 src/scan/wrong-subject
ATTEST api dqsubject scan trivy scan-key 990 80 src/scan/right-subject
QUORUM prod critical gated 2 same-key-ok hard
MEMBER gated build github fulcio 300 50 src/build/ repo:team/build
MEMBER gated scan trivy fulcio 300 50 src/scan/ repo:team/security
REQUEST api dqsubject 1100
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["build-key", "scan-key"]


def test_brutal_hard_delegated_untrusted_key_can_satisfy_policy_only_through_valid_chain(tmp_path):
    """Untrusted attestation keys can satisfy policy only through timestamp, subject, and source-scoped delegation."""
    graph = """
KEY root fulcio repo:root 1 5000 1
KEY mid fulcio repo:team/intermediate 1 5000 0
KEY leaf fulcio repo:team/release 1 5000 0
KEY badleaf fulcio repo:other/release 1 5000 0
IMAGE api ddelegate prod critical
ATTEST api ddelegate slsa github badleaf 1020 99 src/release/bad-subject
ATTEST api ddelegate slsa github leaf 1010 90 src/release/good
DELEGATE root mid 900 1200 repo:team/ src/release/
DELEGATE mid leaf 900 1200 repo:team/release src/release/
DELEGATE mid badleaf 900 1200 repo:team/release src/release/
REQUIRE prod critical slsa github fulcio 200 50 hard repo:team/release src/release/
REQUEST api ddelegate 1100
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["key"] == "leaf"


def test_brutal_hard_delegation_revocation_and_cycles_do_not_create_trust(tmp_path):
    """Revoked intermediate keys and delegation cycles must not bootstrap trust for otherwise untrusted keys."""
    graph = """
KEY root fulcio repo:root 1 5000 1
KEY mid fulcio repo:team/mid 1 5000 0
KEY leaf fulcio repo:team/leaf 1 5000 0
KEY cycleA fulcio repo:team/cycleA 1 5000 0
KEY cycleB fulcio repo:team/cycleB 1 5000 0
IMAGE api dcycle prod critical
ATTEST api dcycle slsa github leaf 1000 80 src/release/leaf
ATTEST api dcycle scan trivy cycleA 1000 80 src/release/cycle
DELEGATE root mid 900 1200 repo:team/ src/release/
DELEGATE mid leaf 900 1200 repo:team/leaf src/release/
DELEGATE cycleA cycleB 900 1200 repo:team/ src/release/
DELEGATE cycleB cycleA 900 1200 repo:team/ src/release/
REVOKE mid 950 1050
REQUIRE prod critical slsa github fulcio 200 50 hard repo:team/ src/release/
REQUIRE prod critical scan trivy fulcio 200 50 warn repo:team/ src/release/
REQUEST api dcycle 1100
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "denied"
    assert actual["decisions"][0]["reasons"] == ["missing:slsa:github"]
    assert actual["decisions"][0]["warnings"] == ["missing:scan:trivy"]
    assert actual["evidence"] == []


def test_brutal_hard_transparency_bundle_rejects_newer_invalid_evidence(tmp_path):
    """Transparency bundles can invalidate the newest signature and force fallback to older included evidence."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dtlog prod critical
ATTEST api dtlog slsa github k 1200 120 src-new-invalid-bundle
ATTEST api dtlog slsa github k 1100 110 src-old-valid-bundle
LOGROOT rekor root-good 1000 1300 1
LOGROOT rekor root-bad 1000 1300 0
BUNDLE 120 rekor 1200 121 root-bad
BUNDLE 110 rekor 1100 111 root-good
REQUIRE prod critical slsa github fulcio 300 50 hard
REQUEST api dtlog 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src-old-valid-bundle"


def test_brutal_hard_transparency_bundle_time_and_tree_size_boundaries(tmp_path):
    """Bundle integrated_time and tree_size must both match the attestation inclusion proof rules."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dtbounds prod standard
ATTEST api dtbounds slsa github k 1000 90 src-equal-tree
ATTEST api dtbounds scan trivy k 1010 91 src-wrong-time
ATTEST api dtbounds sbom syft k 1020 92 src-good
LOGROOT rekor root 900 1100 1
BUNDLE 90 rekor 1000 90 root
BUNDLE 91 rekor 1009 92 root
BUNDLE 92 rekor 1020 93 root
REQUIRE prod standard slsa github fulcio 200 50 warn
REQUIRE prod standard scan trivy fulcio 200 50 warn
REQUIRE prod standard sbom syft fulcio 200 50 hard
REQUEST api dtbounds 1050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["decisions"][0]["warnings"] == ["missing:slsa:github", "missing:scan:trivy"]
    assert actual["evidence"][0]["predicate"] == "sbom"


def test_brutal_hard_quorum_bundle_validation_changes_global_selection(tmp_path):
    """Quorum selection must ignore invalid bundled candidates before optimizing distinct-key evidence."""
    graph = """
KEY buildA fulcio repo:build 1 5000 1
KEY buildB fulcio repo:build 1 5000 1
KEY scanA fulcio repo:scan 1 5000 1
IMAGE api dtquorum prod critical
ATTEST api dtquorum build github buildA 1200 200 src/build/new-invalid
ATTEST api dtquorum build github buildB 1190 190 src/build/older-valid
ATTEST api dtquorum scan trivy scanA 1185 185 src/scan/valid
LOGROOT rekor root 1000 1300 1
BUNDLE 200 rekor 1200 201 missing-root
BUNDLE 190 rekor 1190 191 root
BUNDLE 185 rekor 1185 186 root
QUORUM prod critical release 2 distinct-key hard
MEMBER release build github fulcio 300 50 src/build repo:build
MEMBER release scan trivy fulcio 300 50 src/scan repo:scan
REQUEST api dtquorum 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["buildB", "scanA"]


def test_brutal_hard_checkpoint_consistency_rejects_root_without_trusted_predecessor(tmp_path):
    """A trusted log root is not enough when matching checkpoints demand a trusted predecessor chain."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dtcheckpoint prod critical
ATTEST api dtcheckpoint slsa github k 1200 300 src/new-bad-checkpoint
ATTEST api dtcheckpoint slsa github k 1150 250 src/old-good-checkpoint
LOGROOT rekor prev-root 900 1100 1
LOGROOT rekor new-root 1100 1300 1
LOGROOT rekor alt-root 1000 1300 1
BUNDLE 300 rekor 1200 301 new-root
BUNDLE 250 rekor 1150 251 alt-root
CHECKPOINT rekor 301 new-root missing-prev 240 1
CHECKPOINT rekor 251 alt-root prev-root 200 1
REQUIRE prod critical slsa github fulcio 400 50 hard
REQUEST api dtcheckpoint 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/old-good-checkpoint"


def test_brutal_hard_checkpoint_trust_and_tree_monotonicity_boundaries(tmp_path):
    """Checkpoint proofs must be trusted and strictly increase tree size before evidence can be accepted."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dtcpbound prod standard
ATTEST api dtcpbound build github k 1000 400 src/build
ATTEST api dtcpbound scan trivy k 1010 410 src/scan
ATTEST api dtcpbound sbom syft k 1020 420 src/sbom
LOGROOT rekor prev 900 980 1
LOGROOT rekor root-build 990 1200 1
LOGROOT rekor root-scan 990 1200 1
LOGROOT rekor root-sbom 990 1200 1
BUNDLE 400 rekor 1000 401 root-build
BUNDLE 410 rekor 1010 411 root-scan
BUNDLE 420 rekor 1020 421 root-sbom
CHECKPOINT rekor 401 root-build prev 401 1
CHECKPOINT rekor 411 root-scan prev 390 0
CHECKPOINT rekor 421 root-sbom prev 390 1
REQUIRE prod standard build github fulcio 200 50 warn
REQUIRE prod standard scan trivy fulcio 200 50 warn
REQUIRE prod standard sbom syft fulcio 200 50 hard
REQUEST api dtcpbound 1050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["decisions"][0]["warnings"] == ["missing:build:github", "missing:scan:trivy"]
    assert actual["evidence"][0]["predicate"] == "sbom"


def test_brutal_hard_source_scoped_compromise_falls_back_without_global_revocation(tmp_path):
    """A compromise can invalidate only matching source prefixes while leaving the same key usable elsewhere."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dcomp prod critical
ATTEST api dcomp slsa github k 1200 90 src/prod/new-compromised
ATTEST api dcomp slsa github k 1180 80 src/dev/new-safe-wrong-prefix
ATTEST api dcomp slsa github k 1100 70 src/prod/old-safe
REQUIRE prod critical slsa github fulcio 400 50 hard * src/prod/
REQUEST api dcomp 1250
COMPROMISE k 1150 1250 src/prod/
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/prod/old-safe"


def test_brutal_hard_compromised_delegation_parent_blocks_leaf_chain(tmp_path):
    """Compromise checks apply to every key in a delegation chain, not only the attesting leaf key."""
    graph = """
KEY root fulcio repo:root 1 5000 1
KEY mid fulcio repo:mid 1 5000 0
KEY leaf fulcio repo:leaf 1 5000 0
KEY fallback fulcio repo:leaf 1 5000 1
IMAGE api dchain prod critical
ATTEST api dchain slsa github leaf 1200 100 src/release/delegated
ATTEST api dchain slsa github fallback 1100 90 src/release/fallback
DELEGATE root mid 1000 1300 repo:mid src/release/
DELEGATE mid leaf 1000 1300 repo:leaf src/release/
COMPROMISE mid 1150 1250 src/release/
REQUIRE prod critical slsa github fulcio 400 50 hard repo:leaf src/release/
REQUEST api dchain 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["key"] == "fallback"


def test_brutal_hard_quorum_compromise_and_checkpoint_interlock(tmp_path):
    """Quorum optimization must filter compromised and checkpoint-invalid candidates before scoring."""
    graph = """
KEY build1 fulcio repo:build 1 5000 1
KEY build2 fulcio repo:build 1 5000 1
KEY scan1 fulcio repo:scan 1 5000 1
IMAGE api dqattack prod critical
ATTEST api dqattack build github build1 1300 510 src/build/compromised
ATTEST api dqattack build github build2 1250 500 src/build/safe
ATTEST api dqattack scan trivy scan1 1240 490 src/scan/safe
LOGROOT rekor base 100 1000 1
LOGROOT rekor root 1000 1400 1
BUNDLE 510 rekor 1300 511 root
BUNDLE 500 rekor 1250 501 root
BUNDLE 490 rekor 1240 491 root
CHECKPOINT rekor 511 root missing 400 1
CHECKPOINT rekor 501 root base 300 1
CHECKPOINT rekor 491 root base 300 1
COMPROMISE build1 1200 1350 src/build/
QUORUM prod critical attack-gate 2 distinct-key hard
MEMBER attack-gate build github fulcio 300 50 src/build repo:build
MEMBER attack-gate scan trivy fulcio 300 50 src/scan repo:scan
REQUEST api dqattack 1350
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["build2", "scan1"]


def test_brutal_hard_splitview_report_rejects_otherwise_valid_bundle(tmp_path):
    """A trusted split-view report invalidates a root even when bundle, root, and checkpoint all verify."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE api dsplit prod critical
ATTEST api dsplit slsa github k 1300 610 src/split/bad-root
ATTEST api dsplit slsa github k 1240 600 src/split/good-root
LOGROOT rekor base 100 1000 1
LOGROOT rekor root-bad 1000 1400 1
LOGROOT rekor root-good 1000 1400 1
BUNDLE 610 rekor 1300 611 root-bad
BUNDLE 600 rekor 1240 601 root-good
CHECKPOINT rekor 611 root-bad base 500 1
CHECKPOINT rekor 601 root-good base 500 1
SPLITVIEW rekor 611 root-bad 1
REQUIRE prod critical slsa github fulcio 400 50 hard * src/split/
REQUEST api dsplit 1350
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/split/good-root"


def test_brutal_hard_untrusted_splitview_is_ignored_but_trusted_one_blocks_quorum(tmp_path):
    """Only trusted split-view evidence blocks transparency roots, and quorum must re-optimize after filtering."""
    graph = """
KEY build1 fulcio repo:build 1 5000 1
KEY build2 fulcio repo:build 1 5000 1
KEY scan1 fulcio repo:scan 1 5000 1
IMAGE api dqsplit prod critical
ATTEST api dqsplit build github build1 1300 710 src/build/untrusted-report
ATTEST api dqsplit build github build2 1260 700 src/build/trusted-fallback
ATTEST api dqsplit scan trivy scan1 1250 690 src/scan/valid
LOGROOT rekor base 100 1000 1
LOGROOT rekor rootA 1000 1400 1
LOGROOT rekor rootB 1000 1400 1
BUNDLE 710 rekor 1300 711 rootA
BUNDLE 700 rekor 1260 701 rootB
BUNDLE 690 rekor 1250 691 rootB
CHECKPOINT rekor 711 rootA base 500 1
CHECKPOINT rekor 701 rootB base 500 1
CHECKPOINT rekor 691 rootB base 500 1
SPLITVIEW rekor 711 rootA 0
SPLITVIEW rekor 701 rootB 0
SPLITVIEW rekor 711 rootA 1
QUORUM prod critical splitq 2 distinct-key hard
MEMBER splitq build github fulcio 400 50 src/build repo:build
MEMBER splitq scan trivy fulcio 400 50 src/scan repo:scan
REQUEST api dqsplit 1350
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["build2", "scan1"]


@pytest.mark.parametrize("seed", [7101, 7102, 7103, 7104, 7105, 7106])
def test_brutal_hard_generated_revocation_scope_and_duplicate_policy_mesh(seed: int, tmp_path):
    """Generated meshes stress fallback evidence, duplicate requirements, scoped policies, revocation, and warnings."""
    rng = random.Random(seed)
    lines = []
    for i in range(7):
        trusted = 0 if i == 5 else 1
        issuer = "fulcio" if i % 3 != 1 else "other"
        lines.append(f"KEY k{i} {issuer} ci {rng.randint(1, 400)} {rng.randint(1000, 2400)} {trusted}")
    envs = ["prod", "staging"]
    tiers = ["critical", "standard"]
    for i in range(10):
        lines.append(f"IMAGE svc{i} dg{i} {envs[i % 2]} {tiers[(i // 2) % 2]}")
        for pred, builder in [("slsa", "github"), ("scan", "trivy"), ("sbom", "syft")]:
            for _ in range(rng.randint(1, 2)):
                lines.append(f"ATTEST svc{i} dg{i} {pred} {builder} k{rng.randrange(7)} {rng.randint(500, 1800)} {rng.randint(1, 120)} src{i}{pred}{rng.randrange(9)}")
    lines.extend([
        "REQUIRE prod critical slsa github fulcio 900 30 hard",
        "REQUIRE prod critical slsa github fulcio 900 30 hard",
        "REQUIRE prod critical scan trivy fulcio 900 20 warn",
        "REQUIRE staging standard slsa github fulcio 700 20 hard",
        "REQUIRE staging standard sbom syft fulcio 700 20 warn",
        "REQUIRE staging critical scan trivy fulcio 700 20 warn",
    ])
    for i in rng.sample(range(10), 6):
        lines.append(f"REQUEST svc{i} dg{i} {rng.randint(1000, 1900)}")
    for i in rng.sample(range(7), 3):
        lines.append(f"REVOKE k{i}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [9101, 9102, 9103, 9104])
def test_brutal_hard_generated_transparency_bundle_mesh(seed: int, tmp_path):
    """Generated cases mix trusted roots, invalid bundles, fallback signatures, warnings, and quorum evidence."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor rootA 500 2500 1",
        "LOGROOT rekor rootB 500 2500 0",
        "LOGROOT mirror rootM 800 2200 1",
    ]
    for i in range(6):
        subject = ["repo:build", "repo:scan", "repo:sbom"][i % 3]
        lines.append(f"KEY tk{i} fulcio {subject} 1 4000 1")
    for img in range(6):
        lines.append(f"IMAGE svc{img} td{img} {'prod' if img % 2 == 0 else 'staging'} {'critical' if img % 3 != 1 else 'standard'}")
        for j, (pred, builder, prefix) in enumerate([("build", "github", "src/build"), ("scan", "trivy", "src/scan"), ("sbom", "syft", "src/sbom")]):
            for alt in range(2):
                key = f"tk{rng.randrange(6)}"
                ts = 900 + img * 70 + j * 15 + alt * 5
                log_index = 300 + img * 20 + j * 3 + alt
                root = "rootA" if (img + j + alt + seed) % 4 else "rootB"
                tree_size = log_index + 1 if alt or root == "rootA" else log_index
                lines.append(f"ATTEST svc{img} td{img} {pred} {builder} {key} {ts} {log_index} {prefix}/svc{img}/{alt}")
                lines.append(f"BUNDLE {log_index} rekor {ts} {tree_size} {root}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 900 50 hard repo:build src/build",
        "REQUIRE prod critical scan trivy fulcio 900 50 warn repo:scan src/scan",
        "QUORUM prod critical release 2 same-key-ok warn",
        "MEMBER release build github fulcio 900 50 src/build repo:build",
        "MEMBER release scan trivy fulcio 900 50 src/scan repo:scan",
        "MEMBER release sbom syft fulcio 900 50 src/sbom repo:sbom",
        "REQUIRE staging standard build github fulcio 800 40 hard repo:build src/build",
    ])
    for img in rng.sample(range(6), 4):
        lines.append(f"REQUEST svc{img} td{img} {rng.randint(1200, 1700)}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [9201, 9202, 9203, 9204])
def test_brutal_hard_generated_checkpoint_consistency_mesh(seed: int, tmp_path):
    """Generated transparency cases require root, bundle, and checkpoint consistency before policy selection."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor base 100 700 1",
        "LOGROOT rekor rootA 700 2200 1",
        "LOGROOT rekor rootB 700 2200 1",
        "LOGROOT rekor rootC 700 2200 1",
    ]
    for i in range(6):
        subject = ["repo:build", "repo:scan", "repo:sbom"][i % 3]
        lines.append(f"KEY ck{i} fulcio {subject} 1 4000 1")
    for img in range(5):
        lines.append(f"IMAGE rel{img} cd{img} prod critical")
        for j, (pred, builder, prefix) in enumerate([("build", "github", "src/build"), ("scan", "trivy", "src/scan"), ("sbom", "syft", "src/sbom")]):
            for alt in range(2):
                key = f"ck{rng.randrange(6)}"
                ts = 900 + img * 80 + j * 20 + alt * 7
                log_index = 500 + img * 30 + j * 4 + alt
                root = ["rootA", "rootB", "rootC"][(img + j + alt + seed) % 3]
                trusted_checkpoint = (img + j + alt + seed) % 4 != 0
                prev_size = 300 + img
                lines.append(f"ATTEST rel{img} cd{img} {pred} {builder} {key} {ts} {log_index} {prefix}/rel{img}/{alt}")
                lines.append(f"BUNDLE {log_index} rekor {ts} {log_index + 1} {root}")
                lines.append(f"CHECKPOINT rekor {log_index + 1} {root} base {prev_size} {1 if trusted_checkpoint else 0}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 900 50 hard repo:build src/build",
        "REQUIRE prod critical scan trivy fulcio 900 50 warn repo:scan src/scan",
        "QUORUM prod critical relq 2 same-key-ok warn",
        "MEMBER relq build github fulcio 900 50 src/build repo:build",
        "MEMBER relq scan trivy fulcio 900 50 src/scan repo:scan",
        "MEMBER relq sbom syft fulcio 900 50 src/sbom repo:sbom",
    ])
    for img in rng.sample(range(5), 3):
        lines.append(f"REQUEST rel{img} cd{img} {rng.randint(1250, 1700)}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [9301, 9302, 9303, 9304])
def test_brutal_hard_generated_compromise_checkpoint_delegation_mesh(seed: int, tmp_path):
    """Generated attack-surface meshes mix source-scoped compromise, delegated keys, checkpoints, and quorums."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor base 100 800 1",
        "LOGROOT rekor root 800 2600 1",
        "KEY root fulcio repo:root 1 5000 1",
    ]
    for i in range(8):
        trusted = 1 if i < 3 else 0
        subject = ["repo:build", "repo:scan", "repo:sbom", "repo:leaf"][i % 4]
        lines.append(f"KEY ak{i} fulcio {subject} 1 5000 {trusted}")
        if not trusted:
            parent = "root" if rng.random() < 0.5 else f"ak{rng.randrange(3)}"
            lines.append(f"DELEGATE {parent} ak{i} 700 2400 {subject} src/")
    for img in range(6):
        lines.append(f"IMAGE app{img} ad{img} prod critical")
        for j, (pred, builder, prefix) in enumerate([("build", "github", "src/build"), ("scan", "trivy", "src/scan"), ("sbom", "syft", "src/sbom")]):
            for alt in range(2):
                key = f"ak{rng.randrange(8)}"
                ts = 1000 + img * 90 + j * 25 + alt * 9
                log_index = 700 + img * 40 + j * 5 + alt
                lines.append(f"ATTEST app{img} ad{img} {pred} {builder} {key} {ts} {log_index} {prefix}/app{img}/{alt}")
                lines.append(f"BUNDLE {log_index} rekor {ts} {log_index + 1} root")
                lines.append(f"CHECKPOINT rekor {log_index + 1} root base {500 + img} {1 if (seed + img + j + alt) % 5 else 0}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 1000 50 hard repo:build src/build",
        "REQUIRE prod critical scan trivy fulcio 1000 50 warn repo:scan src/scan",
        "QUORUM prod critical attack 2 same-key-ok warn",
        "MEMBER attack build github fulcio 1000 50 src/build repo:build",
        "MEMBER attack scan trivy fulcio 1000 50 src/scan repo:scan",
        "MEMBER attack sbom syft fulcio 1000 50 src/sbom repo:sbom",
    ])
    for i in rng.sample(range(8), 3):
        prefix = ["src/build", "src/scan", "src/sbom"][rng.randrange(3)]
        lines.append(f"COMPROMISE ak{i} {rng.randint(950, 1200)} {rng.randint(1350, 1800)} {prefix}")
    for img in rng.sample(range(6), 4):
        lines.append(f"REQUEST app{img} ad{img} {rng.randint(1300, 1900)}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [9401, 9402, 9403])
def test_brutal_hard_generated_splitview_compromise_mesh(seed: int, tmp_path):
    """Generated cases combine split-view reports, compromised keys, checkpoints, and policy warnings."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor base 100 700 1",
        "LOGROOT rekor rootA 700 2400 1",
        "LOGROOT rekor rootB 700 2400 1",
    ]
    for i in range(7):
        subject = ["repo:build", "repo:scan", "repo:sbom"][i % 3]
        lines.append(f"KEY sk{i} fulcio {subject} 1 5000 1")
    for img in range(5):
        lines.append(f"IMAGE pkg{img} sd{img} prod critical")
        for j, (pred, builder, prefix) in enumerate([("build", "github", "src/build"), ("scan", "trivy", "src/scan"), ("sbom", "syft", "src/sbom")]):
            for alt in range(2):
                key = f"sk{rng.randrange(7)}"
                ts = 1000 + img * 100 + j * 30 + alt * 11
                log_index = 900 + img * 50 + j * 6 + alt
                root = "rootA" if (seed + img + j + alt) % 2 else "rootB"
                lines.append(f"ATTEST pkg{img} sd{img} {pred} {builder} {key} {ts} {log_index} {prefix}/pkg{img}/{alt}")
                lines.append(f"BUNDLE {log_index} rekor {ts} {log_index + 1} {root}")
                lines.append(f"CHECKPOINT rekor {log_index + 1} {root} base {600 + img} 1")
                if (seed + img + j + alt) % 5 == 0:
                    lines.append(f"SPLITVIEW rekor {log_index + 1} {root} 1")
    lines.extend([
        "REQUIRE prod critical build github fulcio 1000 50 hard repo:build src/build",
        "REQUIRE prod critical scan trivy fulcio 1000 50 warn repo:scan src/scan",
        "QUORUM prod critical splitmesh 2 same-key-ok warn",
        "MEMBER splitmesh build github fulcio 1000 50 src/build repo:build",
        "MEMBER splitmesh scan trivy fulcio 1000 50 src/scan repo:scan",
        "MEMBER splitmesh sbom syft fulcio 1000 50 src/sbom repo:sbom",
    ])
    for i in rng.sample(range(7), 2):
        lines.append(f"COMPROMISE sk{i} {rng.randint(1000, 1200)} {rng.randint(1350, 1700)} src/")
    for img in rng.sample(range(5), 3):
        lines.append(f"REQUEST pkg{img} sd{img} {rng.randint(1350, 1850)}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


@pytest.mark.parametrize("seed", [8101, 8102, 8103, 8104])
def test_brutal_hard_generated_quorum_revocation_mesh(seed: int, tmp_path):
    """Generated cases combine scoped revocation, source prefixes, duplicate policies, quorum thresholds, and tie-breaks."""
    rng = random.Random(seed)
    lines = []
    for i in range(8):
        issuer = "fulcio" if i != 6 else "other"
        trusted = 1 if i < 3 else 0
        subject = ["repo:team/build", "repo:team/security", "repo:team/sbom", "repo:other"][i % 4]
        lines.append(f"KEY qk{i} {issuer} {subject} {rng.randint(1, 200)} {rng.randint(1900, 3200)} {trusted}")
    for child in range(3, 8):
        parent = rng.randrange(0, child)
        prefix = "repo:team/" if child != 7 else "repo:other"
        source = "src/" if rng.random() > 0.25 else "*"
        lines.append(f"DELEGATE qk{parent} qk{child} {rng.randint(400, 800)} {rng.randint(1700, 2600)} {prefix} {source}")
    envs = ["prod", "staging"]
    tiers = ["critical", "standard"]
    for i in range(9):
        lines.append(f"IMAGE rel{i} qd{i} {envs[i % 2]} {tiers[(i // 2) % 2]}")
        for pred, builder, prefix in [("build", "github", "src/build"), ("scan", "trivy", "src/scan"), ("sbom", "syft", "src/sbom")]:
            for j in range(2):
                key = f"qk{rng.randrange(8)}"
                source = f"{prefix}/rel{i}/{j}" if rng.random() > 0.2 else f"other/rel{i}/{j}"
                lines.append(f"ATTEST rel{i} qd{i} {pred} {builder} {key} {rng.randint(600, 1700)} {rng.randint(10, 140)} {source}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 900 30 hard repo:team/ src/build",
        "QUORUM prod critical release 2 distinct-key hard",
        "MEMBER release build github fulcio 900 20 src/build repo:team/build",
        "MEMBER release scan trivy fulcio 900 20 src/scan repo:team/security",
        "MEMBER release sbom syft fulcio 900 20 src/sbom repo:team/sbom",
        "QUORUM staging standard release 2 same-key-ok warn",
        "REQUIRE staging standard build github fulcio 700 20 hard repo:team/ *",
    ])
    for i in rng.sample(range(9), 6):
        lines.append(f"REQUEST rel{i} qd{i} {rng.randint(1000, 1900)}")
    for i in rng.sample(range(8), 3):
        start = rng.randint(700, 1200)
        lines.append(f"REVOKE qk{i} {start} {start + rng.randint(50, 300)}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_builder_bind_env_source_and_subject_authorization(tmp_path):
    """Builder bindings are env/tier, source-prefix, subject-prefix, trust, and timestamp scoped."""
    graph = """
KEY prod fulcio prod-ci/team-a 1 5000 1
KEY stage fulcio stage-ci/team-a 1 5000 1
KEY bad fulcio prod-ci/team-b 1 5000 1
IMAGE api dbind prod critical
ATTEST api dbind slsa github stage 1300 210 src/prod/stage-subject
ATTEST api dbind slsa github bad 1290 211 src/prod/bad-subject
ATTEST api dbind slsa github prod 1280 212 src/dev/wrong-source
ATTEST api dbind slsa github prod 1270 213 src/prod/good
BIND github fulcio prod-ci/team-a src/prod prod critical 1200 1400 1
BIND github fulcio stage-ci/ src/prod staging critical 1200 1400 1
BIND github fulcio prod-ci/team-a src/prod prod critical 1275 1400 0
REQUIRE prod critical slsa github fulcio 200 200 hard prod-ci/team-a src/prod
REQUEST api dbind 1350
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["evidence"] == [
        {
            "request": "api@dbind",
            "predicate": "slsa",
            "builder": "github",
            "key": "prod",
            "timestamp": 1270,
            "log_index": 213,
            "source_digest": "src/prod/good",
        }
    ]


def test_brutal_hard_bind_absence_is_legacy_but_any_builder_bind_is_strict(tmp_path):
    """A builder with no BIND records keeps legacy behavior, while one stale bind row makes that builder strict."""
    graph = """
KEY k fulcio ci 1 5000 1
IMAGE app dlegacy prod standard
IMAGE cli dstrict prod critical
ATTEST app dlegacy scan trivy k 1500 301 random/source
ATTEST cli dstrict slsa github k 1500 302 src/release
BIND github fulcio ci src/release prod critical 1 1400 1
REQUIRE prod standard scan trivy fulcio 100 300 hard
REQUIRE prod critical slsa github fulcio 100 300 hard
REQUEST app dlegacy 1550
REQUEST cli dstrict 1550
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["decisions"][1]["status"] == "denied"


def test_brutal_hard_quorum_min_source_groups_reoptimizes_distinct_key_selection(tmp_path):
    """Quorum source diversity is part of feasibility and scoring, not a post-filter on greedy best evidence."""
    graph = """
KEY k1 fulcio ci/a 1 5000 1
KEY k2 fulcio ci/b 1 5000 1
KEY k3 fulcio ci/c 1 5000 1
IMAGE api dsrc prod critical
ATTEST api dsrc build github k1 1500 401 mono/build-new
ATTEST api dsrc scan trivy k2 1495 402 mono/scan-new
ATTEST api dsrc provenance tekton k3 1490 403 split/prov
ATTEST api dsrc scan trivy k2 1480 404 split/scan-old
MEMBER release build github fulcio 200 400 mono ci/
MEMBER release scan trivy fulcio 200 400 * ci/
MEMBER release provenance tekton fulcio 200 400 split ci/
QUORUM prod critical release 2 distinct-key hard 2
REQUEST api dsrc 1550
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == [
        "mono/build-new",
        "mono/scan-new",
        "split/prov",
    ]


@pytest.mark.parametrize("seed", [10101, 10102, 10103, 10104])
def test_brutal_hard_generated_case10_bind_and_source_diversity_mesh(seed: int, tmp_path):
    """Generated CASE10-style meshes combine builder bindings, source diversity, revocation, and quorum optimization."""
    rng = random.Random(seed)
    lines = [
        "KEY root fulcio ci/root 1 9000 1",
        "KEY prodA fulcio prod/team-a 1 9000 1",
        "KEY prodB fulcio prod/team-b 1 9000 1",
        "KEY stage fulcio stage/team-a 1 9000 1",
        "KEY leaf fulcio prod/delegated 1 9000 0",
        "DELEGATE root leaf 1 9000 prod/ src/release",
        "BIND github fulcio prod/ src/release prod critical 1000 8000 1",
        "BIND trivy fulcio prod/ scan prod critical 1000 8000 1",
        "BIND tekton fulcio * * prod critical 1000 8000 1",
    ]
    for i in range(6):
        digest = f"dcase10{i}"
        lines.append(f"IMAGE img{i} {digest} prod critical")
        base_time = 1500 + i * 20
        lines.append(f"ATTEST img{i} {digest} build github prodA {base_time + rng.randrange(8)} {500 + i * 10} src/release/build{i}")
        lines.append(f"ATTEST img{i} {digest} build github stage {base_time + 12} {600 + i * 10} src/release/stage{i}")
        lines.append(f"ATTEST img{i} {digest} scan trivy prodB {base_time + rng.randrange(8)} {510 + i * 10} scan/release/scan{i}")
        lines.append(f"ATTEST img{i} {digest} provenance tekton leaf {base_time + rng.randrange(8)} {520 + i * 10} src/release/prov{i}")
        if i % 2 == 0:
            lines.append(f"REVOKE prodA {base_time + 1} {base_time + 30}")
        if i % 3 == 0:
            lines.append(f"COMPROMISE root {base_time - 5} {base_time + 40} src/release/prov")
    lines.extend([
        "REQUIRE prod critical build github fulcio 200 500 hard prod/ src/release",
        "MEMBER case10 build github fulcio 200 500 src/release prod/",
        "MEMBER case10 scan trivy fulcio 200 500 scan prod/",
        "MEMBER case10 provenance tekton fulcio 200 500 src/release prod/",
        "QUORUM prod critical case10 2 distinct-key warn 2",
    ])
    for i in range(6):
        lines.append(f"REQUEST img{i} dcase10{i} {1650 + i * 20}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_embargo_blocks_by_request_or_attestation_time_and_scope(tmp_path):
    """Embargoes are scoped hard gates and trigger on either request time or attestation time."""
    graph = """
KEY k fulcio prod/team 1 5000 1
IMAGE api dembargo prod critical
IMAGE stage dembargo-stage staging critical
ATTEST api dembargo build github k 1180 610 src/release/during-attestation
ATTEST api dembargo build github k 1000 611 src/release/request-window
ATTEST api dembargo build github k 990 612 src/safe/older-valid
ATTEST stage dembargo-stage build github k 1180 613 src/release/staging-safe
EMBARGO prod critical github src/release 1100 1200
REQUIRE prod critical build github fulcio 500 600 hard prod/ *
REQUIRE staging critical build github fulcio 500 600 hard prod/ *
REQUEST api dembargo 1150
REQUEST stage dembargo-stage 1150
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["evidence"][0]["source_digest"] == "src/safe/older-valid"
    assert actual["evidence"][1]["source_digest"] == "src/release/staging-safe"


def test_brutal_hard_embargo_quorum_reoptimizes_after_bind_and_splitview_filters(tmp_path):
    """Embargo filtering composes before quorum optimization with builder bind and transparency checks."""
    graph = """
KEY build fulcio prod/build 1 5000 1
KEY scan fulcio prod/scan 1 5000 1
KEY prov fulcio prod/prov 1 5000 1
LOGROOT rekor base 1 900 1
LOGROOT rekor root 900 5000 1
IMAGE api dincident prod critical
ATTEST api dincident build github build 1300 700 src/release/build-embargoed
ATTEST api dincident build github build 980 701 archive/build-old
ATTEST api dincident scan trivy scan 1290 702 scan/release/scan-new
ATTEST api dincident provenance tekton prov 1280 703 src/release/prov-split
ATTEST api dincident provenance tekton prov 970 704 archive/prov-old
BUNDLE 703 rekor 1280 704 root
CHECKPOINT rekor 704 root base 500 1
SPLITVIEW rekor 704 root 1
BIND github fulcio prod/ archive prod critical 1 5000 1
BIND trivy fulcio prod/ scan prod critical 1 5000 1
BIND tekton fulcio prod/ archive prod critical 1 5000 1
EMBARGO prod critical github src/release 1200 1400
MEMBER incident build github fulcio 500 600 archive prod/
MEMBER incident scan trivy fulcio 500 600 scan prod/
MEMBER incident provenance tekton fulcio 500 600 archive prod/
QUORUM prod critical incident 2 distinct-key hard 2
REQUEST api dincident 1325
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == [
        "archive/build-old",
        "scan/release/scan-new",
        "archive/prov-old",
    ]


@pytest.mark.parametrize("seed", [11101, 11102, 11103, 11104])
def test_brutal_hard_generated_case11_embargo_incident_response_mesh(seed: int, tmp_path):
    """Generated CASE11 meshes force incident embargo, source diversity, bind authorization, and delegated trust together."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor base 1 900 1",
        "LOGROOT rekor root 900 9000 1",
        "KEY root fulcio prod/root 1 9000 1",
        "KEY build fulcio prod/build 1 9000 1",
        "KEY scan fulcio prod/scan 1 9000 1",
        "KEY prov fulcio prod/prov 1 9000 0",
        "DELEGATE root prov 1 9000 prod/prov prov",
        "BIND github fulcio prod/build archive prod critical 1 9000 1",
        "BIND trivy fulcio prod/scan scan prod critical 1 9000 1",
        "BIND tekton fulcio prod/prov prov prod critical 1 9000 1",
        "EMBARGO prod critical github src/release 1500 1700",
        "EMBARGO prod critical tekton src/release 1500 1700",
    ]
    for i in range(5):
        digest = f"dcase11{i}"
        lines.append(f"IMAGE rel{i} {digest} prod critical")
        base_time = 1460 + i * 30
        lines.append(f"ATTEST rel{i} {digest} build github build {base_time + 50} {800 + i * 10} src/release/build{i}")
        lines.append(f"ATTEST rel{i} {digest} build github build {base_time + rng.randrange(10)} {900 + i * 10} archive/build{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {base_time + 45} {810 + i * 10} scan/release/scan{i}")
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {base_time + 48} {820 + i * 10} src/release/prov{i}")
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {base_time + rng.randrange(10)} {920 + i * 10} archive/prov{i}")
        bad_log = 820 + i * 10
        if (seed + i) % 2 == 0:
            lines.append(f"BUNDLE {bad_log} rekor {base_time + 48} {bad_log + 1} root")
            lines.append(f"CHECKPOINT rekor {bad_log + 1} root base 600 1")
            lines.append(f"SPLITVIEW rekor {bad_log + 1} root 1")
        if (seed + i) % 3 == 0:
            lines.append(f"COMPROMISE root {base_time + 40} {base_time + 70} archive/prov")
    lines.extend([
        "REQUIRE prod critical build github fulcio 500 800 hard prod/build archive",
        "MEMBER case11 build github fulcio 500 800 archive prod/build",
        "MEMBER case11 scan trivy fulcio 500 800 scan prod/scan",
        "MEMBER case11 provenance tekton fulcio 500 800 archive prod/prov",
        "QUORUM prod critical case11 2 distinct-key warn 2",
    ])
    for i in range(5):
        lines.append(f"REQUEST rel{i} dcase11{i} {1600 + i * 25}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_chain_requires_prior_valid_build_before_scan(tmp_path):
    """CHAIN rules force evidence to prove ordered provenance, not just local attestation validity."""
    graph = """
KEY k fulcio prod/team 1 5000 1
KEY other other prod/team 1 5000 1
IMAGE api dchain prod critical
ATTEST api dchain scan trivy k 1400 800 scan/new-no-prior
ATTEST api dchain build github other 1380 790 archive/wrong-issuer
ATTEST api dchain scan trivy k 1300 760 scan/has-prior
ATTEST api dchain build github k 1260 750 archive/build-valid
CHAIN prod critical scan trivy build github 80 scan
REQUIRE prod critical scan trivy fulcio 200 700 hard prod/ scan
REQUEST api dchain 1450
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["evidence"][0]["timestamp"] == 1300
    assert actual["evidence"][0]["source_digest"] == "scan/has-prior"


def test_brutal_hard_chain_base_validity_blocks_transparency_and_embargoed_predecessors(tmp_path):
    """Predecessors must pass base trust, transparency, bind, and embargo gates before satisfying a chain."""
    graph = """
KEY k fulcio prod/team 1 5000 1
LOGROOT rekor base 1 900 1
LOGROOT rekor root 900 5000 1
IMAGE api dchainbase prod critical
ATTEST api dchainbase build github k 1200 900 archive/split-build
BUNDLE 900 rekor 1200 901 root
CHECKPOINT rekor 901 root base 700 1
SPLITVIEW rekor 901 root 1
ATTEST api dchainbase scan trivy k 1220 910 scan/bad-predecessor
ATTEST api dchainbase build github k 1000 700 embargo/build
ATTEST api dchainbase scan trivy k 1040 720 scan/embargo-predecessor
ATTEST api dchainbase build github k 900 600 archive/good-build
ATTEST api dchainbase scan trivy k 940 610 scan/good
EMBARGO prod critical github embargo 990 1010
CHAIN prod critical scan trivy build github 50 scan
REQUIRE prod critical scan trivy fulcio 500 600 hard prod/ scan
REQUEST api dchainbase 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["evidence"][0]["source_digest"] == "scan/good"


def test_brutal_hard_chain_quorum_reoptimizes_member_selection_after_provenance_filter(tmp_path):
    """Quorum search must filter chain-invalid member candidates before scoring selected evidence."""
    graph = """
KEY build fulcio prod/build 1 5000 1
KEY scan fulcio prod/scan 1 5000 1
KEY sbom fulcio prod/sbom 1 5000 1
IMAGE api dqchain prod critical
ATTEST api dqchain build github build 1000 1000 archive/build
ATTEST api dqchain scan trivy scan 1100 1010 scan/new-too-late
ATTEST api dqchain scan trivy scan 1040 1020 scan/chained
ATTEST api dqchain sbom syft sbom 1090 1030 sbom/direct
CHAIN prod critical scan trivy build github 50 scan
MEMBER qchain scan trivy fulcio 200 900 scan prod/scan
MEMBER qchain sbom syft fulcio 200 900 sbom prod/sbom
QUORUM prod critical qchain 2 distinct-key hard 2
REQUEST api dqchain 1120
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == ["scan/chained", "sbom/direct"]


def test_brutal_hard_unique_requirement_consumes_evidence_in_policy_order(tmp_path):
    """UNIQUE images cannot reuse the same best attestation for duplicate hard requirements."""
    graph = """
KEY k fulcio prod/build 1 5000 1
IMAGE api dunique prod critical
UNIQUE prod critical
ATTEST api dunique build github k 1500 900 src/newest
ATTEST api dunique build github k 1490 910 src/older-higher-log
REQUIRE prod critical build github fulcio 200 800 hard prod/ src/
REQUIRE prod critical build github fulcio 200 800 hard prod/ src/
REQUEST api dunique 1550
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == ["src/newest", "src/older-higher-log"]
    assert actual["decisions"][0]["status"] == "approved"


def test_brutal_hard_unique_same_key_quorum_needs_distinct_records(tmp_path):
    """same-key-ok still cannot reuse one attestation record when UNIQUE is active."""
    graph = """
KEY k fulcio prod/shared 1 5000 1
IMAGE api duniqueq prod critical
UNIQUE prod critical
ATTEST api duniqueq scan trivy k 1600 950 scan/shared-new
ATTEST api duniqueq scan trivy k 1580 960 scan/shared-old
MEMBER reuse scan trivy fulcio 200 900 scan prod/
MEMBER reuse scan trivy fulcio 200 900 scan prod/
QUORUM prod critical reuse 2 same-key-ok hard 1
REQUEST api duniqueq 1650
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == ["scan/shared-new", "scan/shared-old"]
    assert actual["decisions"][0]["status"] == "approved"


def test_brutal_hard_unique_cross_policy_quorum_reoptimizes_after_requirement(tmp_path):
    """A later quorum must avoid evidence consumed by an earlier requirement and still optimize globally."""
    graph = """
KEY build fulcio prod/build 1 5000 1
KEY scan fulcio prod/scan 1 5000 1
KEY prov fulcio prod/prov 1 5000 1
IMAGE api duniquemesh prod critical
UNIQUE prod critical
ATTEST api duniquemesh build github build 1700 1000 src/build-new
ATTEST api duniquemesh build github build 1660 1001 archive/build-old
ATTEST api duniquemesh scan trivy scan 1690 1010 scan/scan-new
ATTEST api duniquemesh provenance tekton prov 1680 1020 prov/prov-new
REQUIRE prod critical build github fulcio 200 900 hard prod/ src/
MEMBER mesh build github fulcio 300 900 archive prod/
MEMBER mesh scan trivy fulcio 300 900 scan prod/
MEMBER mesh provenance tekton fulcio 300 900 prov prod/
QUORUM prod critical mesh 3 distinct-key hard 3
REQUEST api duniquemesh 1720
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == [
        "src/build-new",
        "archive/build-old",
        "scan/scan-new",
        "prov/prov-new",
    ]
    assert actual["decisions"][0]["status"] == "approved"


def test_brutal_hard_json_escaping_for_opaque_security_tokens(tmp_path):
    """Opaque token fields must be serialized as valid JSON even when they contain JSON metacharacters."""
    graph = (
        "KEY k fulcio prod/build 1 5000 1\n"
        "IMAGE api dqjson prod critical\n"
        "ATTEST api dqjson build github k 1500 900 src/quote\\\"slash\\\\ctrl\x01\n"
        "REQUIRE prod critical build github fulcio 200 800 hard prod/ src/\n"
        "REQUEST api dqjson 1550\n"
    )
    actual, raw = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert "\\u0001" in raw
    assert actual["evidence"][0]["source_digest"] == "src/quote\\\"slash\\\\ctrl\x01"


def test_brutal_hard_unique_reservation_is_request_local(tmp_path):
    """UNIQUE reserves evidence within one request only; later requests for the same image start fresh."""
    graph = """
KEY k fulcio prod/build 1 5000 1
IMAGE api dlocal prod critical
UNIQUE prod critical
ATTEST api dlocal build github k 1500 900 src/new
ATTEST api dlocal build github k 1490 901 src/old
REQUIRE prod critical build github fulcio 200 800 hard prod/ src/
REQUIRE prod critical build github fulcio 200 800 hard prod/ src/
REQUEST api dlocal 1550
REQUEST api dlocal 1560
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [e["source_digest"] for e in actual["evidence"]] == ["src/new", "src/old", "src/new", "src/old"]


@pytest.mark.parametrize("seed", [15101, 15102, 15103, 15104])
def test_brutal_hard_generated_unique_policy_state_mesh(seed: int, tmp_path):
    """Generated UNIQUE meshes combine reservation state with chain, delegation, bind, revoke, and quorum search."""
    rng = random.Random(seed)
    lines = [
        "KEY root fulcio prod/root 1 9000 1",
        "KEY build fulcio prod/build 1 9000 1",
        "KEY scan fulcio prod/scan 1 9000 1",
        "KEY prov fulcio prod/prov 1 9000 0",
        "KEY sbom fulcio prod/sbom 1 9000 1",
        "DELEGATE root prov 1 9000 prod/prov prov",
        "BIND github fulcio prod/build * prod critical 1 9000 1",
        "BIND trivy fulcio prod/scan scan prod critical 1 9000 1",
        "BIND tekton fulcio prod/prov prov prod critical 1 9000 1",
        "BIND syft fulcio prod/sbom sbom prod critical 1 9000 1",
        "CHAIN prod critical scan trivy build github 70 scan",
        "UNIQUE prod critical",
    ]
    expected_requests = []
    for i in range(4):
        digest = f"dcase15{i}"
        expected_requests.append(f"rel{i}@{digest}")
        base_time = 2200 + i * 80 + rng.randrange(7)
        build_new = base_time + 40
        build_old = base_time + 10
        scan_good = build_new + 55
        lines.append(f"IMAGE rel{i} {digest} prod critical")
        lines.append(f"ATTEST rel{i} {digest} build github build {build_new} {1500 + i * 30} src/release/build{i}")
        lines.append(f"ATTEST rel{i} {digest} build github build {build_old} {1501 + i * 30} archive/build{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {build_new + 95} {1510 + i * 30} scan/too-late{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {scan_good} {1511 + i * 30} scan/release/good{i}")
        prov_new = base_time + 58
        prov_old = base_time + 8
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {prov_new} {1520 + i * 30} prov/prov-new{i}")
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {prov_old} {1521 + i * 30} prov/prov-old{i}")
        sbom_times = [base_time + 70, base_time + 60, base_time + 50]
        for j, ts in enumerate(sbom_times):
            lines.append(f"ATTEST rel{i} {digest} sbom syft sbom {ts} {1530 + i * 30 + j} sbom/doc{i}-{j}")
        if (seed + i) % 2 == 0:
            lines.append(f"COMPROMISE root {prov_new - 1} {prov_new + 1} prov/prov-new{i}")
        if (seed + i) % 3 == 0:
            lines.append(f"REVOKE sbom {sbom_times[0] - 1} {sbom_times[0] + 1}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 300 1400 hard prod/build src/release",
        "MEMBER mesh build github fulcio 400 1400 archive prod/build",
        "MEMBER mesh scan trivy fulcio 400 1400 scan prod/scan",
        "MEMBER mesh provenance tekton fulcio 400 1400 prov prod/prov",
        "QUORUM prod critical mesh 3 distinct-key hard 3",
        "MEMBER repeated sbom syft fulcio 400 1400 sbom prod/sbom",
        "MEMBER repeated sbom syft fulcio 400 1400 sbom prod/sbom",
        "QUORUM prod critical repeated 2 same-key-ok hard 1",
    ])
    for i in range(4):
        lines.append(f"REQUEST rel{i} dcase15{i} {2380 + i * 80}")
    graph = "\n".join(lines) + "\n"
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [d["request"] for d in actual["decisions"]] == expected_requests
    assert all(d["status"] == "approved" for d in actual["decisions"])
    for request_id in expected_requests:
        used_sources = [e["source_digest"] for e in actual["evidence"] if e["request"] == request_id]
        assert len(used_sources) == 6
        assert len(used_sources) == len(set(used_sources))


@pytest.mark.parametrize("seed", [16101, 16102, 16103])
def test_brutal_hard_generated_layered_attack_surface_mesh(seed: int, tmp_path):
    """A single generated mesh composes hold activation, transparency rejection, delegation compromise, chain, bind, and UNIQUE."""
    rng = random.Random(seed)
    lines = [
        "LOGROOT rekor base 1 2000 1",
        "LOGROOT rekor root 2000 9000 1",
        "KEY root fulcio prod/root 1 9000 1",
        "KEY build fulcio prod/build 1 9000 1",
        "KEY scan fulcio prod/scan 1 9000 1",
        "KEY prov fulcio prod/prov 1 9000 0",
        "KEY sbom fulcio prod/sbom 1 9000 1",
        "KEY marker fulcio incident/marker 1 9000 1",
        "DELEGATE root prov 1 9000 prod/prov prov",
        "BIND github fulcio prod/build * prod critical 1 9000 1",
        "BIND trivy fulcio prod/scan scan prod critical 1 9000 1",
        "BIND tekton fulcio prod/prov prov prod critical 1 9000 1",
        "BIND syft fulcio prod/sbom sbom prod critical 1 9000 1",
        "HOLD prod critical github src/release hold sentinel fulcio holdsrc 2400 4000",
        "CHAIN prod critical scan trivy build github 80 scan",
        "UNIQUE prod critical",
    ]
    expected_requests = []
    for i in range(3):
        digest = f"dcase16{i}"
        expected_requests.append(f"rel{i}@{digest}")
        base_time = 2500 + i * 160 + rng.randrange(9)
        build_primary = base_time + 40
        build_alt = base_time + 25
        scan_primary = base_time + 95
        scan_alt = base_time + 85
        prov_primary = base_time + 100
        prov_alt = base_time + 70
        lines.append(f"IMAGE rel{i} {digest} prod critical")
        lines.append(f"ATTEST rel{i} {digest} hold sentinel marker {base_time + 5} {2100 + i * 50} holdsrc/marker{i}")
        lines.append(f"ATTEST rel{i} {digest} build github build {base_time + 60} {2110 + i * 50} src/release/held-build{i}")
        lines.append(f"ATTEST rel{i} {digest} build github build {build_primary} {2111 + i * 50} archive/build-primary{i}")
        lines.append(f"ATTEST rel{i} {digest} build github build {build_alt} {2112 + i * 50} archive/build-alt{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {base_time + 150} {2120 + i * 50} scan/too-late{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {scan_primary} {2121 + i * 50} scan/primary{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {scan_alt} {2122 + i * 50} scan/alt{i}")
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {prov_primary} {2130 + i * 50} prov/primary{i}")
        lines.append(f"ATTEST rel{i} {digest} provenance tekton prov {prov_alt} {2131 + i * 50} prov/alt{i}")
        lines.append(f"ATTEST rel{i} {digest} sbom syft sbom {base_time + 105} {2140 + i * 50} sbom/primary{i}")
        lines.append(f"ATTEST rel{i} {digest} sbom syft sbom {base_time + 90} {2141 + i * 50} sbom/alt{i}")
        if (seed + i) % 2 == 0:
            tree_size = 2131 + i * 50
            lines.append(f"BUNDLE {2130 + i * 50} rekor {prov_primary} {tree_size} root")
            lines.append(f"CHECKPOINT rekor {tree_size} root base 1900 1")
            lines.append(f"SPLITVIEW rekor {tree_size} root 1")
        if (seed + i) % 3 == 0:
            lines.append(f"COMPROMISE root {prov_primary - 2} {prov_primary + 2} prov/primary{i}")
    lines.extend([
        "REQUIRE prod critical build github fulcio 500 2000 hard prod/build archive",
        "REQUIRE prod critical scan trivy fulcio 500 2000 hard prod/scan scan",
        "MEMBER layered build github fulcio 500 2000 archive prod/build",
        "MEMBER layered scan trivy fulcio 500 2000 scan prod/scan",
        "MEMBER layered provenance tekton fulcio 500 2000 prov prod/prov",
        "QUORUM prod critical layered 3 distinct-key hard 3",
        "MEMBER repeated-sbom sbom syft fulcio 500 2000 sbom prod/sbom",
        "MEMBER repeated-sbom sbom syft fulcio 500 2000 sbom prod/sbom",
        "QUORUM prod critical repeated-sbom 2 same-key-ok hard 1",
    ])
    for i in range(3):
        lines.append(f"REQUEST rel{i} dcase16{i} {2700 + i * 160}")
    graph = "\n".join(lines) + "\n"
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [d["request"] for d in actual["decisions"]] == expected_requests
    assert all(d["status"] == "approved" for d in actual["decisions"])
    for request_id in expected_requests:
        sources = [e["source_digest"] for e in actual["evidence"] if e["request"] == request_id]
        assert len(sources) == 7
        assert len(sources) == len(set(sources))
        assert not any("held" in source or "too-late" in source for source in sources)


def test_brutal_hard_layered_attack_surface_denies_when_every_fallback_is_poisoned(tmp_path):
    """A release is denied when hold, split-view, chain, bind, and revocation remove every apparent fallback."""
    graph = """
LOGROOT rekor old 1 1000 1
LOGROOT rekor root 1000 5000 1
KEY build fulcio prod/build 1 5000 1
KEY scan fulcio prod/scan 1 5000 1
KEY marker fulcio incident/marker 1 5000 1
IMAGE api dpoison prod critical
ATTEST api dpoison hold sentinel marker 1100 100 holdsrc/active
ATTEST api dpoison build github build 1450 900 src/release/held
ATTEST api dpoison build github build 1400 901 archive/splitview
BUNDLE 901 rekor 1400 902 root
CHECKPOINT rekor 902 root old 800 1
SPLITVIEW rekor 902 root 1
ATTEST api dpoison build github build 1300 902 other/unbound
ATTEST api dpoison scan trivy scan 1480 910 scan/no-valid-predecessor
HOLD prod critical github src/release hold sentinel fulcio holdsrc 1000 2000
BIND github fulcio prod/build archive prod critical 1 5000 1
CHAIN prod critical scan trivy build github 80 scan
REQUIRE prod critical build github fulcio 300 800 hard prod/build *
REQUIRE prod critical scan trivy fulcio 300 800 warn prod/scan scan
REQUEST api dpoison 1500
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"] == [{
        "request": "api@dpoison",
        "status": "denied",
        "reasons": ["missing:build:github"],
        "warnings": ["missing:scan:trivy"],
    }]
    assert actual["evidence"] == []
    assert actual["summary"] == {"requests": 1, "approved": 0, "denied": 1, "warnings": 1}


@pytest.mark.parametrize("seed", [12101, 12102, 12103, 12104])
def test_brutal_hard_generated_case12_chain_policy_mesh(seed: int, tmp_path):
    """Generated CASE12 meshes combine chain provenance, incident gates, bind constraints, and quorum diversity."""
    rng = random.Random(seed)
    lines = [
        "KEY build fulcio prod/build 1 9000 1",
        "KEY scan fulcio prod/scan 1 9000 1",
        "KEY sbom fulcio prod/sbom 1 9000 1",
        "KEY other other prod/build 1 9000 1",
        "BIND github fulcio prod/build archive prod critical 1 9000 1",
        "BIND trivy fulcio prod/scan scan prod critical 1 9000 1",
        "BIND syft fulcio prod/sbom sbom prod critical 1 9000 1",
        "CHAIN prod critical scan trivy build github 70 scan",
        "EMBARGO prod critical github archive/bad 1500 1700",
    ]
    for i in range(6):
        digest = f"dcase12{i}"
        lines.append(f"IMAGE rel{i} {digest} prod critical")
        base_time = 1450 + i * 25
        good_build_ts = base_time + rng.randrange(10)
        lines.append(f"ATTEST rel{i} {digest} build github build {good_build_ts} {1000 + i * 20} archive/build{i}")
        lines.append(f"ATTEST rel{i} {digest} build github other {good_build_ts + 5} {1001 + i * 20} archive/wrong-issuer{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {good_build_ts + 60} {1010 + i * 20} scan/chained{i}")
        lines.append(f"ATTEST rel{i} {digest} scan trivy scan {good_build_ts + 100} {1011 + i * 20} scan/too-late{i}")
        lines.append(f"ATTEST rel{i} {digest} sbom syft sbom {good_build_ts + 40} {1020 + i * 20} sbom/direct{i}")
        if (seed + i) % 2 == 0:
            lines.append(f"ATTEST rel{i} {digest} build github build {good_build_ts + 20} {1030 + i * 20} archive/bad{i}")
        if (seed + i) % 3 == 0:
            lines.append(f"REVOKE scan {good_build_ts + 90} {good_build_ts + 130}")
    lines.extend([
        "REQUIRE prod critical scan trivy fulcio 300 900 hard prod/scan scan",
        "MEMBER q12 scan trivy fulcio 300 900 scan prod/scan",
        "MEMBER q12 sbom syft fulcio 300 900 sbom prod/sbom",
        "QUORUM prod critical q12 2 distinct-key warn 2",
    ])
    for i in range(6):
        lines.append(f"REQUEST rel{i} dcase12{i} {1600 + i * 20}")
    assert_matches("\n".join(lines) + "\n", tmp_path)


def test_brutal_hard_witness_quorum_rejects_duplicate_key_shortcut(tmp_path):
    """Transparency witnesses must satisfy distinct-key quorum instead of counting duplicate rows."""
    graph = """
KEY signer fulcio prod/build 1 2000 1
KEY w1 witness witness/root 1 2000 1
IMAGE api dwit prod critical
ATTEST api dwit build github signer 900 80 src/release
LOGROOT rekor rootA 1 2000 1
BUNDLE 80 rekor 900 100 rootA
WITNESSREQ rekor root 2 distinct-key 100 wit/
WITNESS rekor 100 rootA w1 890 wit/a 1
WITNESS rekor 100 rootA w1 891 wit/b 1
REQUIRE prod critical build github fulcio 200 50 hard prod/build src/
REQUEST api dwit 1000
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "denied"
    assert actual["decisions"][0]["reasons"] == ["missing:build:github"]
    assert actual["evidence"] == []


def test_brutal_hard_delegated_witnesses_obey_revocation_compromise_and_source_scope(tmp_path):
    """Witness quorums reuse key delegation, revocation, compromise, source-prefix, and age gates."""
    graph = """
KEY signer fulcio prod/build 1 5000 1
KEY wroot witness witness/root 1 5000 1
KEY wchild witness witness/leaf 1 5000 0
KEY wbad witness witness/bad 1 5000 1
DELEGATE wroot wchild 1 5000 witness/ wit/
IMAGE svc ddel prod critical
ATTEST svc ddel build github signer 1200 300 src/release
LOGROOT rekor trustedRoot 1 5000 1
BUNDLE 300 rekor 1200 500 trustedRoot
WITNESSREQ rekor trusted 2 distinct-key 100 wit/
WITNESS rekor 500 trustedRoot wbad 1195 bad/source 1
WITNESS rekor 500 trustedRoot wroot 1190 wit/root 1
WITNESS rekor 500 trustedRoot wchild 1185 wit/leaf 1
WITNESS rekor 500 trustedRoot wchild 1100 wit/stale 1
COMPROMISE wbad 1180 1210 bad/
REQUIRE prod critical build github fulcio 300 200 hard prod/build src/
REQUEST svc ddel 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert len(actual["evidence"]) == 1
    assert actual["evidence"][0]["source_digest"] == "src/release"


def test_brutal_hard_witnessed_hold_marker_changes_release_decision(tmp_path):
    """Hold activation depends on the marker's transparency bundle satisfying witness quorum."""
    without_witness = """
KEY signer fulcio prod/build 1 5000 1
KEY marker fulcio incident/marker 1 5000 1
KEY w1 witness witness/a 1 5000 1
KEY w2 witness witness/b 1 5000 1
IMAGE api dhold prod critical
ATTEST api dhold hold sentinel marker 1000 50 holdsrc/marker
ATTEST api dhold build github signer 1100 60 src/release
LOGROOT rekor rootM 1 5000 1
BUNDLE 50 rekor 1000 90 rootM
WITNESSREQ rekor root 2 distinct-key 100 wit/
HOLD prod critical github src/ hold sentinel fulcio holdsrc 900 1300
REQUIRE prod critical build github fulcio 300 40 hard prod/build src/
REQUEST api dhold 1150
"""
    with_witness = without_witness.replace(
        "HOLD prod critical",
        "WITNESS rekor 90 rootM w1 995 wit/a 1\nWITNESS rekor 90 rootM w2 996 wit/b 1\nHOLD prod critical",
    )
    actual_without, _ = run_auditor(SRC, without_witness, tmp_path)
    actual_with, _ = run_auditor(SRC, with_witness, tmp_path)
    assert actual_without == solve(without_witness)
    assert actual_with == solve(with_witness)
    assert actual_without["decisions"][0]["status"] == "approved"
    assert actual_with["decisions"][0]["status"] == "denied"
    assert actual_with["decisions"][0]["reasons"] == ["missing:build:github"]


@pytest.mark.parametrize("seed", [17101, 17102, 17103, 17104])
def test_brutal_hard_generated_witness_transparency_mesh(seed: int, tmp_path):
    """Generated witness meshes combine bundle alternatives, delegation, split-view, stale rows, and distinct keys."""
    rng = random.Random(seed)
    lines = [
        "KEY signer fulcio prod/build 1 9000 1",
        "KEY wroot witness witness/root 1 9000 1",
        "KEY wa witness witness/a 1 9000 1",
        "KEY wb witness witness/b 1 9000 1",
        "KEY wc witness witness/c 1 9000 0",
        "DELEGATE wroot wc 1 9000 witness/ wit/",
        "LOGROOT rekor prev 1 500 1",
        "WITNESSREQ rekor root 2 distinct-key 150 wit/",
    ]
    expected_statuses = []
    for idx in range(6):
        name = f"mesh{idx}"
        digest = f"dw{seed}{idx}"
        ts = 1500 + idx * 30 + rng.randrange(3)
        log_index = 600 + idx * 10
        tree = log_index + 20
        root = f"root{seed}{idx}"
        lines.extend([
            f"IMAGE {name} {digest} prod critical",
            f"ATTEST {name} {digest} build github signer {ts} {log_index} src/release/{idx}",
            f"LOGROOT rekor {root} 1000 9000 1",
            f"BUNDLE {log_index} rekor {ts} {tree} {root}",
            f"CHECKPOINT rekor {tree} {root} prev 400 1",
        ])
        mode = idx % 4
        if mode == 0:
            lines.extend([
                f"WITNESS rekor {tree} {root} wa {ts - 5} wit/a/{idx} 1",
                f"WITNESS rekor {tree} {root} wb {ts - 4} wit/b/{idx} 1",
            ])
            expected_statuses.append("approved")
        elif mode == 1:
            lines.extend([
                f"WITNESS rekor {tree} {root} wa {ts - 5} wit/a/{idx} 1",
                f"WITNESS rekor {tree} {root} wa {ts - 4} wit/dup/{idx} 1",
            ])
            expected_statuses.append("denied")
        elif mode == 2:
            lines.extend([
                f"WITNESS rekor {tree} {root} wa {ts - 200} wit/stale/{idx} 1",
                f"WITNESS rekor {tree} {root} wb {ts - 4} wit/b/{idx} 1",
            ])
            expected_statuses.append("denied")
        else:
            alt_root = f"rootAlt{seed}{idx}"
            alt_tree = tree + 5
            lines.extend([
                f"SPLITVIEW rekor {tree} {root} 1",
                f"LOGROOT rekor {alt_root} 1000 9000 1",
                f"BUNDLE {log_index} rekor {ts} {alt_tree} {alt_root}",
                f"CHECKPOINT rekor {alt_tree} {alt_root} prev 400 1",
                f"WITNESS rekor {alt_tree} {alt_root} wroot {ts - 7} wit/root/{idx} 1",
                f"WITNESS rekor {alt_tree} {alt_root} wc {ts - 6} wit/leaf/{idx} 1",
            ])
            expected_statuses.append("approved")
        lines.append(f"REQUEST {name} {digest} {ts + 20}")
    lines.append("REQUIRE prod critical build github fulcio 300 500 hard prod/build src/")
    graph = "\n".join(lines) + "\n"
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [d["status"] for d in actual["decisions"]] == expected_statuses
    assert actual["summary"]["approved"] == expected_statuses.count("approved")
    assert actual["summary"]["denied"] == expected_statuses.count("denied")


def test_brutal_hard_multiple_witness_requirements_all_bind_same_bundle(tmp_path):
    """Every matching WITNESSREQ must pass; satisfying only the broad requirement is not enough."""
    graph = """
KEY signer fulcio prod/build 1 4000 1
KEY wa witness witness/a 1 4000 1
KEY wb witness witness/b 1 4000 1
KEY wc witness witness/c 1 4000 1
IMAGE api dallreq prod critical
ATTEST api dallreq build github signer 2000 700 src/release
LOGROOT rekor root-secure 1 4000 1
BUNDLE 700 rekor 2000 800 root-secure
WITNESSREQ rekor * 2 distinct-key 100 wit/
WITNESSREQ rekor root-sec 2 distinct-key 100 secure/
WITNESS rekor 800 root-secure wa 1998 wit/a 1
WITNESS rekor 800 root-secure wb 1997 wit/b 1
WITNESS rekor 800 root-secure wc 1996 secure/c 1
REQUIRE prod critical build github fulcio 300 600 hard prod/build src/
REQUEST api dallreq 2050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "denied"
    assert actual["decisions"][0]["reasons"] == ["missing:build:github"]


def test_brutal_hard_alternate_bundle_must_reoptimize_after_witness_failure(tmp_path):
    """A bundle with a valid root but failed witnesses must not block a later valid bundle alternative."""
    graph = """
KEY signer fulcio prod/build 1 4000 1
KEY wa witness witness/a 1 4000 1
KEY wb witness witness/b 1 4000 1
IMAGE api dalt prod critical
ATTEST api dalt build github signer 2100 710 src/release
LOGROOT rekor root-bad 1 4000 1
LOGROOT rekor root-good 1 4000 1
BUNDLE 710 rekor 2100 820 root-bad
BUNDLE 710 rekor 2100 830 root-good
WITNESSREQ rekor root 2 distinct-key 100 wit/
WITNESS rekor 820 root-bad wa 2090 bad/a 1
WITNESS rekor 820 root-bad wb 2091 bad/b 1
WITNESS rekor 830 root-good wa 2092 wit/a 1
WITNESS rekor 830 root-good wb 2093 wit/b 1
REQUIRE prod critical build github fulcio 300 600 hard prod/build src/
REQUEST api dalt 2150
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["log_index"] == 710


def test_brutal_hard_same_key_witness_rows_count_but_unique_policy_evidence_still_reoptimizes(tmp_path):
    """same-key-ok witness rows are bundle facts, while UNIQUE still controls emitted policy evidence."""
    graph = """
KEY signer fulcio prod/build 1 5000 1
KEY scanner fulcio prod/scan 1 5000 1
KEY wa witness witness/a 1 5000 1
IMAGE api dwuniq prod critical
UNIQUE prod critical
ATTEST api dwuniq build github signer 2500 900 src/release/a
ATTEST api dwuniq build github signer 2490 901 src/release/b
ATTEST api dwuniq scan trivy scanner 2510 902 scan/release
LOGROOT rekor rootU 1 5000 1
BUNDLE 900 rekor 2500 1000 rootU
BUNDLE 901 rekor 2490 1001 rootU
BUNDLE 902 rekor 2510 1002 rootU
WITNESSREQ rekor root 2 same-key-ok 200 wit/
WITNESS rekor 1000 rootU wa 2498 wit/a 1
WITNESS rekor 1000 rootU wa 2497 wit/b 1
WITNESS rekor 1001 rootU wa 2488 wit/c 1
WITNESS rekor 1001 rootU wa 2487 wit/d 1
WITNESS rekor 1002 rootU wa 2508 wit/e 1
WITNESS rekor 1002 rootU wa 2507 wit/f 1
REQUIRE prod critical build github fulcio 300 800 hard prod/build src/
REQUIRE prod critical build github fulcio 300 800 hard prod/build src/
QUORUM prod critical qscan 1 same-key-ok hard 1
MEMBER qscan scan trivy fulcio 300 800 scan prod/scan
REQUEST api dwuniq 2550
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["source_digest"] for e in actual["evidence"]] == ["src/release/a", "src/release/b", "scan/release"]


def test_brutal_hard_keyscope_blocks_chain_predecessor_and_forces_fallback(tmp_path):
    """KEYSCOPE applies to CHAIN predecessors, so a newer predecessor can be unusable while an older scoped one works."""
    graph = """
KEY build fulcio prod/build 1 5000 1
KEY scan fulcio prod/scan 1 5000 1
IMAGE api dscopechain prod critical
KEYSCOPE build prod critical github src/good 1 5000 1
ATTEST api dscopechain build github build 1000 100 src/bad/newer
ATTEST api dscopechain build github build 950 90 src/good/older
ATTEST api dscopechain scan trivy scan 1010 110 scan/release
CHAIN prod critical scan trivy build github 100 scan
REQUIRE prod critical scan trivy fulcio 200 80 hard prod/scan scan
REQUEST api dscopechain 1050
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "scan/release"


def test_brutal_hard_keyscope_quorum_reoptimizes_after_env_tier_and_source_scope(tmp_path):
    """Quorum selection must discard attestations whose key scopes only authorize other env/tier/source lanes."""
    graph = """
KEY a fulcio prod/a 1 5000 1
KEY b fulcio prod/b 1 5000 1
KEY c fulcio prod/c 1 5000 1
IMAGE api dscopeq prod critical
KEYSCOPE a prod standard github src/release 1 5000 1
KEYSCOPE a prod critical github src/other 1 5000 1
KEYSCOPE b prod critical github src/release 1 5000 1
KEYSCOPE c prod critical trivy scan/release 1 5000 1
ATTEST api dscopeq build github a 1200 200 src/release/a
ATTEST api dscopeq build github b 1190 201 src/release/b
ATTEST api dscopeq scan trivy c 1210 202 scan/release/c
MEMBER scoped build github fulcio 300 100 src/release prod/
MEMBER scoped scan trivy fulcio 300 100 scan/release prod/
QUORUM prod critical scoped 2 distinct-key hard 2
REQUEST api dscopeq 1250
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert [e["key"] for e in actual["evidence"]] == ["b", "c"]


def test_brutal_hard_keyscope_prevents_hold_marker_activation_when_marker_key_is_out_of_scope(tmp_path):
    """Hold markers use the requested env/tier and marker builder for KEYSCOPE checks."""
    graph = """
KEY signer fulcio prod/build 1 5000 1
KEY marker fulcio incident/marker 1 5000 1
IMAGE api dscopehold prod critical
KEYSCOPE marker staging critical sentinel holdsrc 1 5000 1
ATTEST api dscopehold hold sentinel marker 1000 10 holdsrc/active
ATTEST api dscopehold build github signer 1100 20 src/release
HOLD prod critical github src/ hold sentinel fulcio holdsrc 900 1300
REQUIRE prod critical build github fulcio 300 10 hard prod/build src/
REQUEST api dscopehold 1150
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/release"


def test_brutal_hard_rootpin_rejects_unpinned_bundle_and_retries_pinned_alternative(tmp_path):
    """ROOTPIN is env-scoped and bundle-specific, so the auditor must skip an otherwise valid unpinned root."""
    graph = """
KEY signer fulcio prod/build 1 5000 1
KEY wa witness witness/a 1 5000 1
KEY wb witness witness/b 1 5000 1
IMAGE api dpin prod critical
ATTEST api dpin build github signer 1500 300 src/release
LOGROOT rekor evilroot 1 5000 1
LOGROOT rekor goodroot-prod 1 5000 1
BUNDLE 300 rekor 1500 400 evilroot
BUNDLE 300 rekor 1500 401 goodroot-prod
ROOTPIN prod critical rekor goodroot 1 5000 1
WITNESSREQ rekor * 2 distinct-key 100 wit/
WITNESS rekor 400 evilroot wa 1490 wit/a 1
WITNESS rekor 400 evilroot wb 1491 wit/b 1
WITNESS rekor 401 goodroot-prod wa 1492 wit/a 1
WITNESS rekor 401 goodroot-prod wb 1493 wit/b 1
REQUIRE prod critical build github fulcio 300 200 hard prod/build src/
REQUEST api dpin 1550
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"
    assert actual["evidence"][0]["source_digest"] == "src/release"


def test_brutal_hard_rootpin_controls_hold_marker_activation_by_requested_environment(tmp_path):
    """Hold marker transparency uses the requested image env/tier for root pin checks."""
    graph = """
KEY signer fulcio prod/build 1 5000 1
KEY marker fulcio incident/marker 1 5000 1
IMAGE api drootmark prod critical
ATTEST api drootmark hold sentinel marker 1000 70 holdsrc/marker
ATTEST api drootmark build github signer 1100 80 src/release
LOGROOT rekor staging-root 1 5000 1
BUNDLE 70 rekor 1000 120 staging-root
ROOTPIN prod critical rekor prod-root 1 5000 1
ROOTPIN staging critical rekor staging-root 1 5000 1
HOLD prod critical github src/ hold sentinel fulcio holdsrc 900 1300
REQUIRE prod critical build github fulcio 300 70 hard prod/build src/
REQUEST api drootmark 1150
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "approved"


def test_brutal_hard_rootpin_blocks_chain_predecessor_even_when_leaf_bundle_is_valid(tmp_path):
    """CHAIN predecessor transparency must obey root pins, not just the selected leaf attestation."""
    graph = """
KEY build fulcio prod/build 1 6000 1
KEY scan fulcio prod/scan 1 6000 1
IMAGE api drootchain prod critical
ATTEST api drootchain build github build 2000 500 src/build
ATTEST api drootchain scan trivy scan 2050 520 scan/release
LOGROOT rekor badroot 1 6000 1
LOGROOT rekor prodroot 1 6000 1
BUNDLE 500 rekor 2000 700 badroot
BUNDLE 520 rekor 2050 720 prodroot
ROOTPIN prod critical rekor prodroot 1 6000 1
CHAIN prod critical scan trivy build github 100 scan
REQUIRE prod critical scan trivy fulcio 300 500 hard prod/scan scan
REQUEST api drootchain 2100
"""
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert actual["decisions"][0]["status"] == "denied"
    assert actual["decisions"][0]["reasons"] == ["missing:scan:trivy"]


@pytest.mark.parametrize("seed", [18101, 18102, 18103, 18104])
def test_brutal_hard_generated_rootpin_witness_bundle_mesh(seed: int, tmp_path):
    """Generated root-pin meshes force global bundle reoptimization under witnesses, split views, and env scope."""
    rng = random.Random(seed)
    lines = [
        "KEY signer fulcio prod/build 1 9000 1",
        "KEY witnessA witness witness/a 1 9000 1",
        "KEY witnessB witness witness/b 1 9000 1",
        "KEY witnessC witness witness/c 1 9000 1",
        "LOGROOT rekor oldroot 1 500 1",
        "ROOTPIN prod critical rekor prodroot 1 9000 1",
        "ROOTPIN staging critical rekor stagingroot 1 9000 1",
        "WITNESSREQ rekor * 2 distinct-key 200 witness/",
    ]
    expected = []
    for idx in range(8):
        env = "prod" if idx % 2 == 0 else "staging"
        tier = "critical"
        name = f"pinmesh{idx}"
        digest = f"drp{seed}{idx}"
        ts = 2400 + idx * 25 + rng.randrange(4)
        log_index = 900 + idx * 10
        bad_root = f"wrongroot-{seed}-{idx}"
        good_root = f"{env}root-{seed}-{idx}"
        bad_tree = log_index + 30
        good_tree = log_index + 31
        lines.extend([
            f"IMAGE {name} {digest} {env} {tier}",
            f"ATTEST {name} {digest} build github signer {ts} {log_index} src/release/{idx}",
            f"LOGROOT rekor {bad_root} 1 9000 1",
            f"LOGROOT rekor {good_root} 1 9000 1",
            f"BUNDLE {log_index} rekor {ts} {bad_tree} {bad_root}",
            f"BUNDLE {log_index} rekor {ts} {good_tree} {good_root}",
            f"CHECKPOINT rekor {bad_tree} {bad_root} oldroot 400 1",
            f"CHECKPOINT rekor {good_tree} {good_root} oldroot 400 1",
            f"WITNESS rekor {bad_tree} {bad_root} witnessA {ts - 5} witness/a/{idx} 1",
            f"WITNESS rekor {bad_tree} {bad_root} witnessB {ts - 4} witness/b/{idx} 1",
        ])
        mode = idx % 4
        if mode == 0:
            lines.extend([
                f"WITNESS rekor {good_tree} {good_root} witnessA {ts - 3} witness/a/{idx} 1",
                f"WITNESS rekor {good_tree} {good_root} witnessB {ts - 2} witness/b/{idx} 1",
            ])
            expected.append("approved")
        elif mode == 1:
            lines.extend([
                f"WITNESS rekor {good_tree} {good_root} witnessA {ts - 3} witness/a/{idx} 1",
                f"WITNESS rekor {good_tree} {good_root} witnessA {ts - 2} witness/dup/{idx} 1",
            ])
            expected.append("denied")
        elif mode == 2:
            lines.extend([
                f"SPLITVIEW rekor {good_tree} {good_root} 1",
                f"WITNESS rekor {good_tree} {good_root} witnessA {ts - 3} witness/a/{idx} 1",
                f"WITNESS rekor {good_tree} {good_root} witnessB {ts - 2} witness/b/{idx} 1",
            ])
            expected.append("denied")
        else:
            lines.extend([
                f"WITNESS rekor {good_tree} {good_root} witnessB {ts - 300} witness/stale/{idx} 1",
                f"WITNESS rekor {good_tree} {good_root} witnessC {ts - 2} witness/c/{idx} 1",
            ])
            expected.append("denied")
        lines.append(f"REQUEST {name} {digest} {ts + 50}")
    lines.append("REQUIRE prod critical build github fulcio 500 800 hard prod/build src/")
    lines.append("REQUIRE staging critical build github fulcio 500 800 hard prod/build src/")
    graph = "\n".join(lines) + "\n"
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [row["status"] for row in actual["decisions"]] == expected
    assert actual["summary"]["approved"] == expected.count("approved")
    assert actual["summary"]["denied"] == expected.count("denied")


@pytest.mark.parametrize("seed", [19101, 19102, 19103, 19104])
def test_brutal_hard_generated_full_attack_surface_supermesh(seed: int, tmp_path):
    """Generated supermesh combines root pins, witnesses, key scopes, bind, chain, hold, unique, and quorum search."""
    rng = random.Random(seed)
    lines = [
        "KEY buildA fulcio prod/build/A 1 9000 1",
        "KEY buildB fulcio prod/build/B 1 9000 1",
        "KEY scanK fulcio prod/scan 1 9000 1",
        "KEY marker fulcio incident/marker 1 9000 1",
        "KEY witnessA witness witness/a 1 9000 1",
        "KEY witnessB witness witness/b 1 9000 1",
        "LOGROOT rekor prevroot 1 500 1",
        "ROOTPIN prod critical rekor prodroot 1 9000 1",
        "WITNESSREQ rekor prodroot 2 distinct-key 250 witness/",
        "BIND github fulcio prod/build src/ prod critical 1 9000 1",
        "BIND trivy fulcio prod/scan scan/ prod critical 1 9000 1",
        "BIND sentinel fulcio incident/marker holdsrc prod critical 1 9000 1",
        "KEYSCOPE buildA prod critical github src/ 1 9000 1",
        "KEYSCOPE buildB prod critical github src/good 1 9000 1",
        "KEYSCOPE scanK prod critical trivy scan/ 1 9000 1",
        "KEYSCOPE marker prod critical sentinel holdsrc 1 9000 1",
        "CHAIN prod critical scan trivy build github 160 scan/",
        "HOLD prod critical github src/held hold sentinel fulcio holdsrc 1 9000",
        "EMBARGO prod critical github src/embargo 1 9000",
        "UNIQUE prod critical",
        "REQUIRE prod critical build github fulcio 500 100 hard prod/build src/",
        "REQUIRE prod critical scan trivy fulcio 500 100 hard prod/scan scan/",
        "MEMBER release build github fulcio 500 100 src/ prod/build",
        "MEMBER release scan trivy fulcio 500 100 scan/ prod/scan",
        "QUORUM prod critical release 2 distinct-key hard 2",
    ]

    def add_transparency(log_index, timestamp, root_hash, witness_mode="good"):
        tree = log_index + 100 + rng.randrange(5)
        lines.extend([
            f"LOGROOT rekor {root_hash} 1 9000 1",
            f"BUNDLE {log_index} rekor {timestamp} {tree} {root_hash}",
            f"CHECKPOINT rekor {tree} {root_hash} prevroot 400 1",
        ])
        if witness_mode == "good":
            lines.extend([
                f"WITNESS rekor {tree} {root_hash} witnessA {timestamp - 3} witness/a/{log_index} 1",
                f"WITNESS rekor {tree} {root_hash} witnessB {timestamp - 2} witness/b/{log_index} 1",
            ])
        elif witness_mode == "dup":
            lines.extend([
                f"WITNESS rekor {tree} {root_hash} witnessA {timestamp - 3} witness/a/{log_index} 1",
                f"WITNESS rekor {tree} {root_hash} witnessA {timestamp - 2} witness/dup/{log_index} 1",
            ])
        elif witness_mode == "split":
            lines.extend([
                f"SPLITVIEW rekor {tree} {root_hash} 1",
                f"WITNESS rekor {tree} {root_hash} witnessA {timestamp - 3} witness/a/{log_index} 1",
                f"WITNESS rekor {tree} {root_hash} witnessB {timestamp - 2} witness/b/{log_index} 1",
            ])

    expected = []
    for idx in range(8):
        name = f"super{idx}"
        digest = f"dsuper{seed}{idx}"
        ts = 3000 + idx * 30 + rng.randrange(4)
        base_log = 1200 + idx * 20
        mode = idx % 4
        lines.append(f"IMAGE {name} {digest} prod critical")

        if mode == 0:
            a_source = f"src/good/team{idx}/a"
            b_source = f"src/good/team{idx}/b"
            a_root = f"prodroot-a-{seed}-{idx}"
            b_root = f"prodroot-b-{seed}-{idx}"
            expected.append("approved")
        elif mode == 1:
            a_source = f"src/good/team{idx}/a"
            b_source = f"src/good/team{idx}/b"
            a_root = f"badroot-a-{seed}-{idx}"
            b_root = f"prodroot-b-{seed}-{idx}"
            expected.append("denied")
        elif mode == 2:
            a_source = f"src/held/team{idx}/a"
            b_source = f"src/good/team{idx}/b"
            a_root = f"prodroot-a-{seed}-{idx}"
            b_root = f"prodroot-b-{seed}-{idx}"
            expected.append("denied")
        else:
            a_source = f"src/good/team{idx}/a"
            b_source = f"src/embargo/team{idx}/b"
            a_root = f"prodroot-a-{seed}-{idx}"
            b_root = f"prodroot-b-{seed}-{idx}"
            expected.append("denied")

        marker_log = base_log - 5
        lines.append(f"ATTEST {name} {digest} hold sentinel marker {ts - 20} {marker_log} holdsrc/marker/{idx}")
        add_transparency(marker_log, ts - 20, f"prodroot-marker-{seed}-{idx}")

        lines.append(f"ATTEST {name} {digest} build github buildA {ts} {base_log} {a_source}")
        add_transparency(base_log, ts, a_root, "good")
        lines.append(f"ATTEST {name} {digest} build github buildB {ts - 1} {base_log + 1} {b_source}")
        add_transparency(base_log + 1, ts - 1, b_root, "good" if mode != 3 else "dup")
        lines.append(f"ATTEST {name} {digest} scan trivy scanK {ts + 40} {base_log + 2} scan/team{idx}/release")
        add_transparency(base_log + 2, ts + 40, f"prodroot-scan-{seed}-{idx}", "good" if mode != 1 else "split")
        lines.append(f"ATTEST {name} {digest} scan trivy scanK {ts + 39} {base_log + 3} scan/team{idx}/backup")
        add_transparency(base_log + 3, ts + 39, f"prodroot-scan-backup-{seed}-{idx}", "good")
        lines.append(f"REQUEST {name} {digest} {ts + 80}")

    graph = "\n".join(lines) + "\n"
    actual, _ = run_auditor(SRC, graph, tmp_path)
    assert actual == solve(graph)
    assert [row["status"] for row in actual["decisions"]] == expected
    assert actual["summary"]["approved"] == expected.count("approved")
    assert actual["summary"]["denied"] == expected.count("denied")
    approved_sources = [row["source_digest"] for row in actual["evidence"] if row["request"].startswith("super0@")]
    assert approved_sources == ["src/good/team0/a", "scan/team0/release", "src/good/team0/b", "scan/team0/backup"]
