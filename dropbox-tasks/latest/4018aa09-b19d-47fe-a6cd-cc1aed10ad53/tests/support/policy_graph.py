import hashlib
import itertools
import json
from copy import deepcopy


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def merged(env, profile_file):
    evidence = json.loads((env / "evidence/incident.json").read_text())
    profile = json.loads(profile_file.read_text())
    evidence["severity"] = profile["severity"]
    removed = set(profile["remove_witnesses"])
    evidence["witnesses"] = [w for w in evidence["witnesses"] if w["id"] not in removed]
    for row in evidence["revocations"]:
        row.update(profile["revocation_overrides"].get(row["id"], {}))
    for row in evidence["exceptions"]:
        row.update(profile["exception_overrides"].get(row["id"], {}))
    return evidence, profile


def independent_witnesses(evidence, removed=()):
    eligible = [
        w
        for w in evidence["witnesses"]
        if w["id"] not in removed
        and w["incident"] == evidence["incident_id"]
        and w["root"] == evidence["evidence_root"]
        and w["valid_from"] <= w["signed_at"] < w["valid_until"]
    ]
    parents = {w["independence_parent"] for w in eligible}
    return sorted(
        min(w["id"] for w in eligible if w["independence_parent"] == parent)
        for parent in parents
    )


def path_verdicts(evidence, removed_witnesses=()):
    objects = {o["id"]: o for o in evidence["objects"]}
    votes = independent_witnesses(evidence, removed_witnesses)
    threshold = 3 if evidence["severity"] == "CRITICAL" else 2
    unresolved = {
        p
        for c in evidence["conflicts"]
        if c["left"] == c["right"]
        for p in c.get("affects", [])
    }
    result = {}
    for path in evidence["paths"]:
        cert = next(
            objects[x] for x in path["objects"] if objects[x]["kind"] == "certificate"
        )
        compromised_times = [
            objects[x]["compromised_at"]
            for x in path["objects"]
            if objects[x].get("compromised_at")
        ]
        exception = any(
            e["service"] == path["service"]
            and e["path"] == path["id"]
            and e["incident"] == evidence["incident_id"]
            and e["valid_from"] <= evidence["assessment_at"] < e["valid_until"]
            for e in evidence["exceptions"]
        )
        revoked = any(
            r["object"] == cert["id"] and r["published_at"] <= evidence["assessment_at"]
            for r in evidence["revocations"]
        )
        if path["id"] in unresolved:
            reason = "UNRESOLVED_POLICY"
        elif revoked:
            reason = "REVOKED"
        elif (
            compromised_times
            and cert["issued_at"] >= min(compromised_times)
            and not exception
        ):
            reason = "COMPROMISED_PATH"
        elif (
            compromised_times
            and cert["issued_at"] < min(compromised_times)
            and len(votes) < threshold
        ):
            reason = "QUORUM_FAILURE"
        else:
            reason = None
        result[path["id"]] = reason
    return result, votes, threshold


def subject_outcome(evidence, subject_id, removed_witnesses=()):
    """Independently derive one subject's disposition and reason."""
    verdicts, _, _ = path_verdicts(evidence, removed_witnesses)
    subject_paths = [p for p in evidence["paths"] if p["service"] == subject_id]
    accepted = sorted(p["id"] for p in subject_paths if verdicts[p["id"]] is None)
    reasons = sorted(
        verdicts[p["id"]] for p in subject_paths if verdicts[p["id"]] is not None
    )
    if accepted:
        return "RETAIN", "VALID_PATH"
    if "UNRESOLVED_POLICY" in reasons:
        return "MANUAL_REVIEW", reasons[0]
    return "QUARANTINE", reasons[0]


def counterfactual_disposition(evidence, subject_id, changed_fact):
    """Remove the named fact and recompute the complete subject disposition."""
    changed = deepcopy(evidence)
    if changed_fact.startswith("remove witness "):
        witness_id = changed_fact.removeprefix("remove witness ")
        return subject_outcome(changed, subject_id, (witness_id,))[0]
    if changed_fact.startswith("remove exception "):
        exception_id = changed_fact.removeprefix("remove exception ")
        changed["exceptions"] = [
            row for row in changed["exceptions"] if row["id"] != exception_id
        ]
    elif changed_fact.startswith("remove path "):
        path_id = changed_fact.removeprefix("remove path ")
        changed["paths"] = [row for row in changed["paths"] if row["id"] != path_id]
    else:
        raise AssertionError(f"unsupported counterfactual: {changed_fact}")
    return subject_outcome(changed, subject_id)[0]


def expected_rollback_constraints(evidence, unresolved_ids):
    """Derive rollback citations from unresolved conflicts and active exceptions."""
    conflict_cites = {
        cite
        for row in evidence["conflicts"]
        if row["id"] in unresolved_ids
        for cite in row["evidence"]
    }
    exception_cites = {
        row["evidence"]
        for row in evidence["exceptions"]
        if row["incident"] == evidence["incident_id"]
        and row["valid_from"] <= evidence["assessment_at"] < row["valid_until"]
    }
    return sorted(conflict_cites | exception_cites)


def optimal_cut(evidence, verdicts):
    rejected = [p for p in evidence["paths"] if verdicts[p["id"]] is not None]
    accepted = [p for p in evidence["paths"] if verdicts[p["id"]] is None]
    candidates = sorted(o["id"] for o in evidence["objects"] if o["disableable"])
    protected = {
        s["id"]
        for s in evidence["services"]
        if s["mandatory_emergency"]
        and any(
            e["service"] == s["id"]
            and e["valid_from"] <= evidence["assessment_at"] < e["valid_until"]
            for e in evidence["exceptions"]
        )
    }
    ranked = []
    for size in range(len(candidates) + 1):
        for cut in itertools.combinations(candidates, size):
            disabled = set(cut)
            if any(not disabled.intersection(p["objects"]) for p in rejected):
                continue
            if any(
                not any(
                    p["service"] == service and not disabled.intersection(p["objects"])
                    for p in accepted
                )
                for service in protected
            ):
                continue
            lost = {
                s["id"]
                for s in evidence["services"]
                if not any(
                    p["service"] == s["id"] and not disabled.intersection(p["objects"])
                    for p in accepted
                )
            }
            blast = sum(
                s["disruption_weight"] for s in evidence["services"] if s["id"] in lost
            )
            ranked.append((size, blast, cut))
        if ranked:
            break
    return min(ranked) if ranked else None


def commitment(evidence, profile, assessment, plan):
    return (
        b"INC8821\0"
        + hashlib.sha256(canonical({"evidence": evidence, "profile": profile})).digest()
        + hashlib.sha256(canonical(assessment)).digest()
        + hashlib.sha256(canonical(plan)).digest()
    )
