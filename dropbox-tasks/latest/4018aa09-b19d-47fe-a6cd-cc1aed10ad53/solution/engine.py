#!/usr/bin/env python3
import argparse
import hashlib
import itertools
import json
from pathlib import Path


def canon(x):
    return json.dumps(
        x, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def load(env, profile_path):
    base = json.loads((env / "evidence/incident.json").read_text())
    profile = json.loads(profile_path.read_text())
    merged = json.loads(json.dumps(base))
    merged["severity"] = profile["severity"]
    merged["witnesses"] = [
        w for w in merged["witnesses"] if w["id"] not in profile["remove_witnesses"]
    ]
    for r in merged["revocations"]:
        r.update(profile["revocation_overrides"].get(r["id"], {}))
    for e in merged["exceptions"]:
        e.update(profile["exception_overrides"].get(e["id"], {}))
    return merged, profile


def witnesses(d, removed=()):
    groups = {}
    for w in d["witnesses"]:
        if (
            w["id"] in removed
            or w["incident"] != d["incident_id"]
            or w["root"] != d["evidence_root"]
        ):
            continue
        if not (w["valid_from"] <= w["signed_at"] < w["valid_until"]):
            continue
        groups.setdefault(w["independence_parent"], []).append(w["id"])
    return sorted(min(v) for v in groups.values())


def conflicts(d):
    rows = []
    for c in d["conflicts"]:
        a, b = c["left"], c["right"]
        if a["scope"] != b["scope"]:
            cls, src = "SCOPE_DISTINGUISHED", None
        elif a["source"] == b["source"] and a["time"] != b["time"]:
            cls, src = "SUPERSEDED", b["source"]
        elif a["source"] == b["source"]:
            cls, src = "UNRESOLVED", None
        else:
            cls, src = "PRECEDENCE_RESOLVED", a["source"]
        rows.append(
            {
                "conflict_id": c["id"],
                "classification": cls,
                "controlling_source": src,
                "evidence": sorted(c["evidence"]),
            }
        )
    return rows


def assess(d, remove=()):
    objs = {x["id"]: x for x in d["objects"]}
    ws = witnesses(d, remove)
    required = 3 if d["severity"] == "CRITICAL" else 2
    unresolved = {
        p
        for c in d["conflicts"]
        if c["left"]["source"] == c["right"]["source"]
        and c["left"]["time"] == c["right"]["time"]
        for p in c.get("affects", [])
    }
    by_service = {s["id"]: [] for s in d["services"]}
    for p in d["paths"]:
        cert = next(objs[x] for x in p["objects"] if objs[x]["kind"] == "certificate")
        compromised = next(
            (
                objs[x]["compromised_at"]
                for x in p["objects"]
                if objs[x].get("compromised_at")
            ),
            None,
        )
        rev = next((r for r in d["revocations"] if r["object"] == cert["id"]), None)
        exc = next(
            (
                e
                for e in d["exceptions"]
                if e["service"] == p["service"]
                and e["path"] == p["id"]
                and e["incident"] == d["incident_id"]
                and e["valid_from"] <= d["assessment_at"] < e["valid_until"]
            ),
            None,
        )
        reason = None
        if p["id"] in unresolved:
            reason = "UNRESOLVED_POLICY"
        elif rev and (rev["published_at"] <= d["assessment_at"]):
            reason = "REVOKED"
        elif compromised and cert["issued_at"] >= compromised and not exc:
            reason = "COMPROMISED_PATH"
        elif compromised and cert["issued_at"] < compromised and len(ws) < required:
            reason = "QUORUM_FAILURE"
        by_service[p["service"]].append((p, reason, exc))
    out = []
    for sid, vals in sorted(by_service.items()):
        accepted = sorted(p["id"] for p, r, e in vals if r is None)
        rejected = sorted(p["id"] for p, r, e in vals if r)
        reasons = [r for p, r, e in vals if r]
        reason = "VALID_PATH" if accepted else sorted(reasons)[0]
        disposition = (
            "RETAIN"
            if accepted
            else ("MANUAL_REVIEW" if reason == "UNRESOLVED_POLICY" else "QUARANTINE")
        )
        ev = sorted(
            {f"evidence/incident.json#{p['id']}" for p, r, e in vals}
            | {f"evidence/incident.json#{w}" for w in ws}
        )
        if ws:
            changed = f"remove witness {ws[0]}"
            cf = assess_one(d, sid, (ws[0],))[0]
        else:
            ex = next((e["id"] for p, r, e in vals if e), None)
            changed = (
                f"remove exception {ex}" if ex else f"remove path {vals[0][0]['id']}"
            )
            cf = "QUARANTINE" if accepted and len(accepted) == 1 else disposition
        out.append(
            {
                "subject_id": sid,
                "disposition": disposition,
                "reason_code": reason,
                "accepted_paths": accepted,
                "rejected_paths": rejected,
                "compromise_sources": sorted(
                    {
                        "I_RED"
                        for p, r, e in vals
                        if r in {"COMPROMISED_PATH", "QUORUM_FAILURE"}
                    }
                ),
                "evidence": ev,
                "quorum": {"required": required, "counted": len(ws), "witness_ids": ws},
                "counterfactual": {
                    "changed_fact": changed,
                    "resulting_disposition": cf,
                },
            }
        )
    return out


def assess_one(d, sid, remove):
    # counterfactual helper without recursive counterfactual construction
    ws = witnesses(d, remove)
    required = 3 if d["severity"] == "CRITICAL" else 2
    objs = {x["id"]: x for x in d["objects"]}
    valid = False
    unresolved = {
        path_id
        for conflict in d["conflicts"]
        if conflict["left"]["source"] == conflict["right"]["source"]
        and conflict["left"]["time"] == conflict["right"]["time"]
        for path_id in conflict.get("affects", [])
    }
    manual_review = False
    for p in [p for p in d["paths"] if p["service"] == sid]:
        cert = next(objs[x] for x in p["objects"] if objs[x]["kind"] == "certificate")
        comp = next(
            (
                objs[x]["compromised_at"]
                for x in p["objects"]
                if objs[x].get("compromised_at")
            ),
            None,
        )
        rev = any(
            r["object"] == cert["id"] and r["published_at"] <= d["assessment_at"]
            for r in d["revocations"]
        )
        exc = any(
            e["service"] == sid
            and e["path"] == p["id"]
            and e["valid_from"] <= d["assessment_at"] < e["valid_until"]
            for e in d["exceptions"]
        )
        manual_review |= p["id"] in unresolved
        bad = (
            p["id"] in unresolved
            or rev
            or (comp and cert["issued_at"] >= comp and not exc)
            or (comp and cert["issued_at"] < comp and len(ws) < required)
        )
        valid |= not bad
    if valid:
        return ("RETAIN",)
    return ("MANUAL_REVIEW" if manual_review else "QUARANTINE",)


def plan(d, assessments):
    rejected = {p for a in assessments for p in a["rejected_paths"]}
    accepted = {p for a in assessments for p in a["accepted_paths"]}
    paths = {p["id"]: p for p in d["paths"]}
    candidates = sorted(o["id"] for o in d["objects"] if o["disableable"])
    mandatory = {
        s["id"]
        for s in d["services"]
        if s["mandatory_emergency"]
        and any(
            e["service"] == s["id"]
            and e["valid_from"] <= d["assessment_at"] < e["valid_until"]
            for e in d["exceptions"]
        )
    }
    best = None
    for n in range(len(candidates) + 1):
        for cut in itertools.combinations(candidates, n):
            if any(not set(paths[p]["objects"]) & set(cut) for p in rejected):
                continue
            if any(
                not any(
                    p in accepted and not set(paths[p]["objects"]) & set(cut)
                    for p in paths
                    if paths[p]["service"] == s
                )
                for s in mandatory
            ):
                continue
            lost = {
                s["id"]
                for s in d["services"]
                if not any(
                    p in accepted
                    and paths[p]["service"] == s["id"]
                    and not set(paths[p]["objects"]) & set(cut)
                    for p in paths
                )
            }
            blast = sum(
                s["disruption_weight"] for s in d["services"] if s["id"] in lost
            )
            score = (n, blast, cut)
            if best is None or score < best[0]:
                best = (score, list(cut), blast)
        if best:
            break
    cut, blast = (
        (best[1], best[2])
        if best
        else (candidates, sum(s["disruption_weight"] for s in d["services"]))
    )
    groups = {
        "QUARANTINE": "quarantine",
        "RETAIN": "retain",
        "ROTATE": "rotate",
        "MANUAL_REVIEW": "require_manual_review",
    }
    out = {k: [] for k in groups.values()}
    for a in assessments:
        out[groups[a["disposition"]]].append(a["subject_id"])
    unresolved = sorted(
        c["id"]
        for c in d["conflicts"]
        if c["left"]["source"] == c["right"]["source"]
        and c["left"]["scope"] == c["right"]["scope"]
        and c["left"]["time"] == c["right"]["time"]
    )
    rollback = sorted(
        {x for c in d["conflicts"] if c["id"] in unresolved for x in c["evidence"]}
        | {e["evidence"] for e in d["exceptions"]}
    )
    return {
        "incident_id": d["incident_id"],
        "profile": "",
        "quarantine": sorted(out["quarantine"]),
        "retain": sorted(out["retain"]),
        "rotate": sorted(out["rotate"]),
        "require_manual_review": sorted(out["require_manual_review"]),
        "minimum_cut": cut,
        "blast_radius": blast,
        "unresolved_conflicts": unresolved,
        "execution_order": [
            *(f"disable:{x}" for x in cut),
            *(f"quarantine:{x}" for x in sorted(out["quarantine"])),
        ],
        "rollback_constraints": rollback,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--environment", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    for pp in sorted((a.environment / "cases").glob("*.json")):
        d, p = load(a.environment, pp)
        aa = assess(d)
        name = p["profile"]
        report = {
            "incident_id": d["incident_id"],
            "profile": name,
            "policy_revision": d["policy_revision"],
            "evidence_set_digest": hashlib.sha256(
                canon({"evidence": d, "profile": p})
            ).hexdigest(),
            "conflict_classifications": conflicts(d),
            "assessments": aa,
        }
        cp = plan(d, aa)
        cp["profile"] = name
        dest = a.output / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "trust_assessment.json").write_bytes(canon(report))
        (dest / "containment_plan.json").write_bytes(canon(cp))
        (dest / "decision_commitment.bin").write_bytes(
            b"INC8821\0"
            + hashlib.sha256(canon({"evidence": d, "profile": p})).digest()
            + hashlib.sha256(canon(report)).digest()
            + hashlib.sha256(canon(cp)).digest()
        )


if __name__ == "__main__":
    main()
