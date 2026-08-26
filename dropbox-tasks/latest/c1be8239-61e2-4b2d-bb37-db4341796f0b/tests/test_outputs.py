import hashlib
import itertools
import json
import os
import shutil
import subprocess
from pathlib import Path


TASK_ROOT = Path(os.environ.get("TASK_ROOT", "/app/task_file"))
PROJECT = TASK_ROOT / "logseal"
PUBLIC_INPUT = TASK_ROOT / "input_data"


REASON_PREFIX = [
    "bad_signature",
    "unknown_signer",
    "wrong_role",
    "scope_mismatch",
    "cohort_scope",
    "predicate_scope",
    "signer_time_window",
    "digest_mismatch",
    "version_mismatch",
    "revoked_signer",
    "revoked_attestation",
    "unknown_log",
    "unknown_checkpoint",
    "checkpoint_log_mismatch",
    "bad_checkpoint_signature",
    "checkpoint_time_window",
    "checkpoint_after_evaluation",
    "revoked_log",
    "revoked_checkpoint",
    "leaf_hash_mismatch",
    "bad_inclusion_proof",
]


def dump_json(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=False))


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, separators=(",", ":"), sort_keys=False) + "\n" for row in rows))


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def canonical_att(att):
    keys = ["artifact_id", "artifact_version", "predicate", "digest", "issued_at", "signer_id", "log_id", "checkpoint_id"]
    return ("{" + ",".join(json.dumps(k) + ":" + json.dumps(att[k]) for k in keys) + "}").encode()


def canonical_checkpoint(cp):
    keys = ["checkpoint_id", "log_id", "tree_size", "root_hash", "signed_at"]
    return ("{" + ",".join(json.dumps(k) + ":" + json.dumps(cp[k]) for k in keys) + "}").encode()


def sha_hex(data):
    return hashlib.sha256(data).hexdigest()


def sign(secret, payload):
    return hashlib.sha256(secret.encode() + b"\n" + payload).hexdigest()


def is_lhex(value):
    return len(value) % 2 == 0 and all(c in "0123456789abcdef" for c in value)


def combine(left_hex, right_hex):
    return hashlib.sha256(bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hexdigest()


def version_key(version):
    return [int(part) for part in version.split(".")]


def version_lt(left, right):
    a = version_key(left)
    b = version_key(right)
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a < b


def required_for(policy, channel):
    return policy["required_predicates_by_channel"].get(channel, policy["default_required_predicates"])


def log_quorum(policy, channel):
    return policy["log_quorum_by_channel"].get(channel, policy["default_log_quorum"])


def resilience_min_cost(policy, channel):
    return policy["resilience_min_cost_by_channel"].get(channel, policy["default_resilience_min_cost"])


def minimum_cut(policy, required, quorum, evidence):
    signer_domains = sorted({row["signer_domain"] for row in evidence})
    log_domains = sorted({row["log_domain"] for row in evidence})
    domains = [("signer", domain) for domain in signer_domains] + [("log", domain) for domain in log_domains]
    assert len(domains) <= 16
    predicate_order = sorted(required)
    best = None
    for selected_count in range(len(domains) + 1):
        for indexes in itertools.combinations(range(len(domains)), selected_count):
            selected = {domains[index] for index in indexes}
            removed_signers = sorted(domain for kind, domain in selected if kind == "signer")
            removed_logs = sorted(domain for kind, domain in selected if kind == "log")
            surviving = [
                row
                for row in evidence
                if ("signer", row["signer_domain"]) not in selected
                and ("log", row["log_domain"]) not in selected
            ]
            failure = None
            failure_rank = None
            for rank, predicate in enumerate(predicate_order):
                signers = {row["signer_id"] for row in surviving if row["predicate"] == predicate}
                if len(signers) < required[predicate]:
                    failure = f"threshold:{predicate}"
                    failure_rank = rank
                    break
            if failure is None and len({row["log_id"] for row in surviving}) < quorum:
                failure = "log_quorum"
                failure_rank = len(predicate_order)
            if failure is None:
                continue
            cost = sum(policy["signer_domain_costs"][domain] for domain in removed_signers)
            cost += sum(policy["log_domain_costs"][domain] for domain in removed_logs)
            candidate = {
                "cost": cost,
                "failure": failure,
                "signer_domains": removed_signers,
                "log_domains": removed_logs,
            }
            key = (cost, selected_count, failure_rank, removed_signers, removed_logs)
            if best is None or key < best[0]:
                best = (key, candidate)
    return None if best is None else best[1]


def evidence_broken(required, quorum, evidence, removed_signers=frozenset(), removed_logs=frozenset()):
    surviving = [
        row
        for row in evidence
        if row["signer_domain"] not in removed_signers and row["log_domain"] not in removed_logs
    ]
    for predicate, threshold in required.items():
        if len({row["signer_id"] for row in surviving if row["predicate"] == predicate}) < threshold:
            return True
    return len({row["log_id"] for row in surviving}) < quorum


def fleet_resilience_cut(policy, states):
    targets = policy["fleet_resilience_targets_by_channel"]
    direct_targets = policy["fleet_resilience_direct_targets_by_channel"]
    impact_targets = policy["fleet_resilience_impact_targets_by_channel"]
    assert set(targets) == set(direct_targets) == set(impact_targets)
    candidates = {}
    for artifact_id, state in states.items():
        artifact = state["artifact"]
        channel = artifact["channel"]
        if channel not in targets:
            continue
        required = required_for(policy, channel)
        quorum = log_quorum(policy, channel)
        if not evidence_broken(required, quorum, state["evidence"]):
            candidates[artifact_id] = (artifact, required, quorum, state["evidence"])

    signer_domains = sorted({row["signer_domain"] for _, _, _, evidence in candidates.values() for row in evidence})
    log_domains = sorted({row["log_domain"] for _, _, _, evidence in candidates.values() for row in evidence})
    domains = [("signer", domain) for domain in signer_domains] + [("log", domain) for domain in log_domains]
    assert len(domains) <= 18

    def outcome(removed_signers, removed_logs):
        directly_broken = []
        for artifact_id, (_, required, quorum, evidence) in candidates.items():
            if evidence_broken(required, quorum, evidence, set(removed_signers), set(removed_logs)):
                directly_broken.append(artifact_id)

        broken = set(directly_broken)
        cascade_depth = {artifact_id: 0 for artifact_id in directly_broken}
        depth = 1
        while True:
            newly_broken = []
            for artifact_id, (artifact, _, _, _) in candidates.items():
                if artifact_id in broken or artifact["fleet_dependency_threshold"] == 0:
                    continue
                failed_weight = sum(
                    dependency["fleet_weight"]
                    for dependency in artifact["dependencies"]
                    if dependency["artifact_id"] in candidates and dependency["artifact_id"] in broken
                )
                if failed_weight >= artifact["fleet_dependency_threshold"]:
                    newly_broken.append(artifact_id)
            if not newly_broken:
                break
            for artifact_id in newly_broken:
                broken.add(artifact_id)
                cascade_depth[artifact_id] = depth
            depth += 1

        broken_by_channel = {channel: 0 for channel in targets}
        direct_by_channel = {channel: 0 for channel in targets}
        broken_impact_by_channel = {channel: 0 for channel in targets}
        for artifact_id in broken:
            artifact = candidates[artifact_id][0]
            channel = artifact["channel"]
            broken_by_channel[channel] += 1
            broken_impact_by_channel[channel] += artifact["fleet_impact"]
        for artifact_id in directly_broken:
            direct_by_channel[candidates[artifact_id][0]["channel"]] += 1
        if any(broken_by_channel[channel] < target for channel, target in targets.items()):
            return None
        if any(direct_by_channel[channel] < target for channel, target in direct_targets.items()):
            return None
        if any(broken_impact_by_channel[channel] < target for channel, target in impact_targets.items()):
            return None
        return directly_broken, broken, cascade_depth, broken_impact_by_channel

    def outcome_margin(result):
        directly_broken, broken, _, broken_impact_by_channel = result
        slacks = []
        for channel in targets:
            slacks.extend(
                [
                    sum(candidates[artifact_id][0]["channel"] == channel for artifact_id in directly_broken)
                    - direct_targets[channel],
                    sum(candidates[artifact_id][0]["channel"] == channel for artifact_id in broken)
                    - targets[channel],
                    broken_impact_by_channel[channel] - impact_targets[channel],
                ]
            )
        return min(slacks, default=0)

    best = None
    for selected_count in range(len(domains) + 1):
        for indexes in itertools.combinations(range(len(domains)), selected_count):
            selected = {domains[index] for index in indexes}
            removed_signers = sorted(domain for kind, domain in selected if kind == "signer")
            removed_logs = sorted(domain for kind, domain in selected if kind == "log")
            original = outcome(removed_signers, removed_logs)
            if original is None:
                continue
            recovery_breakpoint = None
            recovery_budget = policy["fleet_recovery_domain_budget"]
            recovery_margin = {
                "value": outcome_margin(original),
                "restored_cost": 0,
                "signer_domains": [],
                "log_domains": [],
            }
            for recovered_count in range(1, selected_count + 1):
                for recovered_indexes in itertools.combinations(indexes, recovered_count):
                    recovered = {domains[index] for index in recovered_indexes}
                    effective = selected - recovered
                    effective_signers = [domain for kind, domain in effective if kind == "signer"]
                    effective_logs = [domain for kind, domain in effective if kind == "log"]
                    recovered_signers = sorted(domain for kind, domain in recovered if kind == "signer")
                    recovered_logs = sorted(domain for kind, domain in recovered if kind == "log")
                    recovered_cost = sum(
                        policy["signer_domain_costs"][domain] for domain in recovered_signers
                    ) + sum(policy["log_domain_costs"][domain] for domain in recovered_logs)
                    effective_outcome = outcome(effective_signers, effective_logs)
                    if effective_outcome is not None and recovered_count <= recovery_budget:
                        margin = {
                            "value": outcome_margin(effective_outcome),
                            "restored_cost": recovered_cost,
                            "signer_domains": recovered_signers,
                            "log_domains": recovered_logs,
                        }
                        margin_key = (
                            margin["value"],
                            margin["restored_cost"],
                            margin["signer_domains"],
                            margin["log_domains"],
                        )
                        current_margin_key = (
                            recovery_margin["value"],
                            recovery_margin["restored_cost"],
                            recovery_margin["signer_domains"],
                            recovery_margin["log_domains"],
                        )
                        if margin_key < current_margin_key:
                            recovery_margin = margin
                    if effective_outcome is None:
                        breakpoint = {
                            "count": recovered_count,
                            "cost": recovered_cost,
                            "signer_domains": recovered_signers,
                            "log_domains": recovered_logs,
                        }
                        breakpoint_key = (
                            recovered_count,
                            recovered_cost,
                            recovered_signers,
                            recovered_logs,
                        )
                        if recovery_breakpoint is None or breakpoint_key < recovery_breakpoint[0]:
                            recovery_breakpoint = (breakpoint_key, breakpoint)
                if recovery_breakpoint is not None:
                    break
            if recovery_breakpoint is not None and recovery_breakpoint[1]["count"] <= recovery_budget:
                continue
            directly_broken, broken, cascade_depth, broken_impact_by_channel = original
            cost = sum(policy["signer_domain_costs"][domain] for domain in removed_signers)
            cost += sum(policy["log_domain_costs"][domain] for domain in removed_logs)
            candidate = {
                "cost": cost,
                "shortfall": cost < policy["fleet_resilience_min_cost"],
                "directly_broken_artifacts": sorted(directly_broken),
                "broken_artifacts": sorted(broken),
                "cascade_depth_by_artifact": {
                    artifact_id: cascade_depth[artifact_id] for artifact_id in sorted(broken)
                },
                "broken_impact_by_channel": broken_impact_by_channel,
                "signer_domains": removed_signers,
                "log_domains": removed_logs,
                "recovery_breakpoint": None if recovery_breakpoint is None else recovery_breakpoint[1],
                "recovery_margin": recovery_margin,
            }
            breakpoint_count = len(domains) + 1 if recovery_breakpoint is None else recovery_breakpoint[1]["count"]
            breakpoint_cost = (
                sum(policy["signer_domain_costs"].values()) + sum(policy["log_domain_costs"].values()) + 1
                if recovery_breakpoint is None
                else recovery_breakpoint[1]["cost"]
            )
            key = (
                cost,
                -recovery_margin["value"],
                -breakpoint_count,
                -breakpoint_cost,
                selected_count,
                removed_signers,
                removed_logs,
            )
            if best is None or key < best[0]:
                best = (key, candidate)

    if best is None:
        return {
            "cost": None,
            "shortfall": False,
            "directly_broken_artifacts": [],
            "broken_artifacts": [],
            "cascade_depth_by_artifact": {},
            "broken_impact_by_channel": {channel: 0 for channel in targets},
            "signer_domains": [],
            "log_domains": [],
            "recovery_breakpoint": None,
            "recovery_margin": None,
        }
    return best[1]


def inclusion_ok(att, inclusion, checkpoint):
    if inclusion is None:
        return False
    if inclusion["leaf_index"] < 0 or inclusion["leaf_index"] >= checkpoint["tree_size"]:
        return False
    if not is_lhex(att["leaf_hash"]):
        return False
    current = bytes.fromhex(att["leaf_hash"])
    for item in inclusion["audit_path"]:
        if item["side"] not in {"left", "right"} or not is_lhex(item["hash"]):
            return False
        sibling = bytes.fromhex(item["hash"])
        if item["side"] == "left":
            current = hashlib.sha256(sibling + current).digest()
        else:
            current = hashlib.sha256(current + sibling).digest()
    return current.hex() == checkpoint["root_hash"]


def model(input_dir):
    input_dir = Path(input_dir)
    policy = json.loads((input_dir / "policy.json").read_text())
    logs = {r["log_id"]: r for r in read_jsonl(input_dir / "trusted_logs.jsonl")}
    signers = {r["signer_id"]: r for r in read_jsonl(input_dir / "signers.jsonl")}
    artifacts = read_jsonl(input_dir / "artifacts.jsonl")
    attestations = read_jsonl(input_dir / "attestations.jsonl")
    checkpoints = {r["checkpoint_id"]: r for r in read_jsonl(input_dir / "checkpoints.jsonl")}
    inclusions = {r["attestation_id"]: r for r in read_jsonl(input_dir / "inclusions.jsonl")}
    revocations = read_jsonl(input_dir / "revocations.jsonl")
    eval_time = policy["evaluation_time"]
    def revoked(kind):
        return {r["target_id"] for r in revocations if r["kind"] == kind and r["effective_at"] <= eval_time}

    revoked_signers = revoked("signer")
    revoked_atts = revoked("attestation")
    revoked_logs = revoked("log")
    revoked_checkpoints = revoked("checkpoint")

    states = {}
    for artifact in artifacts:
        required = required_for(policy, artifact["channel"])
        reasons = set()
        accepted = {predicate: {} for predicate in required}
        accepted_logs = set()
        evidence = []
        for att in [row for row in attestations if row["artifact_id"] == artifact["artifact_id"]]:
            usable = True
            payload = canonical_att(att)
            signer = signers.get(att["signer_id"])
            if signer is None:
                reasons.add("unknown_signer")
                usable = False
            else:
                if sign(signer["key_secret"], payload) != att["signature"]:
                    reasons.add("bad_signature")
                    usable = False
                if signer["role"] != "release":
                    reasons.add("wrong_role")
                    usable = False
                if "*" not in signer["artifact_scopes"] and artifact["artifact_id"] not in signer["artifact_scopes"]:
                    reasons.add("scope_mismatch")
                    usable = False
                if artifact["cohort"] not in signer["cohorts"]:
                    reasons.add("cohort_scope")
                    usable = False
                if att["predicate"] not in signer["predicates"]:
                    reasons.add("predicate_scope")
                    usable = False
                if not (signer["not_before"] <= att["issued_at"] <= signer["not_after"]):
                    reasons.add("signer_time_window")
                    usable = False
                if signer["signer_id"] in revoked_signers:
                    reasons.add("revoked_signer")
                    usable = False
            if att["digest"] != artifact["digest"]:
                reasons.add("digest_mismatch")
                usable = False
            if att["artifact_version"] != artifact["version"]:
                reasons.add("version_mismatch")
                usable = False
            if att["attestation_id"] in revoked_atts:
                reasons.add("revoked_attestation")
                usable = False

            log = logs.get(att["log_id"])
            checkpoint = checkpoints.get(att["checkpoint_id"])
            if log is None:
                reasons.add("unknown_log")
                usable = False
            if checkpoint is None:
                reasons.add("unknown_checkpoint")
                usable = False
            if att["log_id"] in revoked_logs:
                reasons.add("revoked_log")
                usable = False
            if checkpoint is not None:
                if checkpoint["log_id"] != att["log_id"]:
                    reasons.add("checkpoint_log_mismatch")
                    usable = False
                if log is not None:
                    if sign(log["log_secret"], canonical_checkpoint(checkpoint)) != checkpoint["signature"]:
                        reasons.add("bad_checkpoint_signature")
                        usable = False
                    if not (log["not_before"] <= checkpoint["signed_at"] <= log["not_after"]):
                        reasons.add("checkpoint_time_window")
                        usable = False
                if checkpoint["signed_at"] > eval_time:
                    reasons.add("checkpoint_after_evaluation")
                    usable = False
                if checkpoint["checkpoint_id"] in revoked_checkpoints:
                    reasons.add("revoked_checkpoint")
                    usable = False
                if sha_hex(payload) != att["leaf_hash"]:
                    reasons.add("leaf_hash_mismatch")
                    usable = False
                if not inclusion_ok(att, inclusions.get(att["attestation_id"]), checkpoint):
                    reasons.add("bad_inclusion_proof")
                    usable = False
            if att["predicate"] not in accepted:
                usable = False
            if usable:
                current = accepted[att["predicate"]].get(att["signer_id"])
                if current is None or att["issued_at"] > current["issued_at"] or (
                    att["issued_at"] == current["issued_at"] and att["attestation_id"] < current["attestation_id"]
                ):
                    accepted[att["predicate"]][att["signer_id"]] = att
                accepted_logs.add(att["log_id"])
                evidence.append({
                    "predicate": att["predicate"],
                    "signer_id": att["signer_id"],
                    "log_id": att["log_id"],
                    "signer_domain": signer["trust_domain"],
                    "log_domain": log["operator_domain"],
                })

        for predicate, threshold in required.items():
            if len(accepted[predicate]) < threshold:
                reasons.add(f"threshold:{predicate}")
        if len(accepted_logs) < log_quorum(policy, artifact["channel"]):
            reasons.add("log_quorum")
        cut = minimum_cut(policy, required, log_quorum(policy, artifact["channel"]), evidence)
        if cut is not None and cut["cost"] < resilience_min_cost(policy, artifact["channel"]):
            reasons.add("resilience_shortfall")
        if eval_time < artifact["rollout_start"] or eval_time > artifact["rollout_end"]:
            reasons.add("rollout_window")
        if artifact["cohort"] not in policy["allowed_cohorts_by_channel"].get(artifact["channel"], []):
            reasons.add("cohort_not_allowed")
        states[artifact["artifact_id"]] = {
            "artifact": artifact,
            "reasons": reasons,
            "accepted": accepted,
            "logs": accepted_logs,
            "evidence": evidence,
            "cut": cut,
            "blockers": [],
        }

    first_phase = {artifact_id: set(state["reasons"]) for artifact_id, state in states.items()}
    for artifact in artifacts:
        blockers = []
        for dep in artifact["dependencies"]:
            target = states.get(dep["artifact_id"])
            if target is None:
                blockers.append(f"missing:{dep['artifact_id']}")
            elif first_phase[dep["artifact_id"]]:
                blockers.append(f"rejected:{dep['artifact_id']}")
            elif version_lt(target["artifact"]["version"], dep["min_version"]):
                blockers.append(f"version:{dep['artifact_id']}")
            elif target["artifact"]["channel"] not in dep["allowed_channels"]:
                blockers.append(f"channel:{dep['artifact_id']}")
        if blockers:
            states[artifact["artifact_id"]]["reasons"].add("dependency_blocked")
            states[artifact["artifact_id"]]["blockers"] = blockers

    rows = []
    for artifact in artifacts:
        state = states[artifact["artifact_id"]]
        required = required_for(policy, artifact["channel"])
        order = REASON_PREFIX + [f"threshold:{p}" for p in sorted(required)] + [
            "log_quorum",
            "resilience_shortfall",
            "rollout_window",
            "cohort_not_allowed",
            "dependency_blocked",
        ]
        reasons = [reason for reason in order if reason in state["reasons"]]
        rows.append({
            "artifact_id": artifact["artifact_id"],
            "version": artifact["version"],
            "channel": artifact["channel"],
            "cohort": artifact["cohort"],
            "status": "accepted" if not reasons else "rejected",
            "reasons": reasons,
            "accepted_signers": {p: sorted(state["accepted"][p]) for p in required},
            "accepted_logs": sorted(state["logs"]),
            "resilience_cut": state["cut"] or {
                "cost": None,
                "failure": None,
                "signer_domains": [],
                "log_domains": [],
            },
            "dependency_blockers": state["blockers"],
        })

    if policy["ordering"] == "artifact_id":
        rows.sort(key=lambda r: (r["artifact_id"], version_key(r["version"]), r["channel"], r["cohort"]))
    else:
        priority = {channel: idx for idx, channel in enumerate(policy["channel_priority"])}
        rows.sort(key=lambda r: (
            0 if r["channel"] in priority else 1,
            priority.get(r["channel"], r["channel"]),
            r["artifact_id"],
            version_key(r["version"]),
            r["cohort"],
        ))
    accepted = sum(1 for row in rows if row["status"] == "accepted")
    return {
        "generated_at": eval_time,
        "artifacts": rows,
        "fleet_resilience_cut": fleet_resilience_cut(policy, states),
        "summary": {"accepted": accepted, "rejected": len(rows) - accepted, "total": len(rows)},
    }


def add_checkpoint(checkpoints, log, checkpoint_id, root_hash, tree_size=1, signed_at="2026-01-10T00:00:00Z"):
    cp = {
        "checkpoint_id": checkpoint_id,
        "log_id": log["log_id"],
        "tree_size": tree_size,
        "root_hash": root_hash,
        "signed_at": signed_at,
        "signature": "",
    }
    cp["signature"] = sign(log["log_secret"], canonical_checkpoint(cp))
    checkpoints.append(cp)
    return cp


def add_attestation(attestations, inclusions, checkpoints, artifact, signer, log, predicate, att_id, checkpoint_id, issued_at="2026-01-09T00:00:00Z", sibling=None):
    att = {
        "attestation_id": att_id,
        "artifact_id": artifact["artifact_id"],
        "artifact_version": artifact["version"],
        "predicate": predicate,
        "digest": artifact["digest"],
        "issued_at": issued_at,
        "signer_id": signer["signer_id"],
        "signature": "",
        "log_id": log["log_id"],
        "leaf_hash": "",
        "checkpoint_id": checkpoint_id,
    }
    payload = canonical_att(att)
    att["signature"] = sign(signer["key_secret"], payload)
    att["leaf_hash"] = sha_hex(payload)
    if sibling is None:
        root = att["leaf_hash"]
        path = []
        tree_size = 1
    else:
        root = combine(att["leaf_hash"], sibling)
        path = [{"side": "right", "hash": sibling}]
        tree_size = 2
    add_checkpoint(checkpoints, log, checkpoint_id, root, tree_size=tree_size)
    attestations.append(att)
    inclusions.append({"attestation_id": att_id, "leaf_index": 0, "audit_path": path})
    return att


def base_fixture(
    path,
    *,
    ordering="artifact_id",
    bad_proof=False,
    revoked_log=False,
    dependency_mode="none",
    log_quorum_stable=1,
    unknown_signer=False,
    unknown_checkpoint=False,
    checkpoint_log_mismatch=False,
    bad_checkpoint_signature=False,
    revoked_signer=False,
    revoked_attestation=False,
    revoked_checkpoint=False,
    signer_time_window=False,
    default_fallback=False,
    bad_signature=False,
    scope_mismatch=False,
    cohort_scope=False,
    predicate_scope=False,
    version_mismatch=False,
    unknown_log=False,
    checkpoint_time_window=False,
    checkpoint_after_evaluation=False,
    leaf_hash_mismatch=False,
    duplicate_signer=False,
    duplicate_signer_tie=False,
    unrequired_predicate=False,
    future_and_unknown_revocations=False,
    missing_inclusion=False,
    negative_leaf_index=False,
    out_of_range_leaf_index=False,
    invalid_proof_hash=False,
    non_lowercase_proof_hash=False,
    invalid_audit_side=False,
    missing_allowed_cohort_channel=False,
    jsonl_empty_lines=False,
    case_sensitive_ids=False,
    inclusive_time_boundaries=False,
    multiple_unlisted_channels=False,
    predicate_threshold_two=False,
    predicate_threshold_two_shortfall=False,
):
    path.mkdir(parents=True, exist_ok=True)
    policy = {
        "evaluation_time": "2026-01-15T00:00:00Z",
        "ordering": ordering,
        "channel_priority": ["stable", "beta"],
        "required_predicates_by_channel": {"stable": {"build": 1, "scan": 1}, "beta": {"build": 1}},
        "default_required_predicates": {"build": 1},
        "log_quorum_by_channel": {"stable": log_quorum_stable},
        "default_log_quorum": 1,
        "resilience_min_cost_by_channel": {"stable": 2, "beta": 1},
        "default_resilience_min_cost": 1,
        "fleet_resilience_targets_by_channel": {"stable": 2},
        "fleet_resilience_direct_targets_by_channel": {"stable": 0},
        "fleet_resilience_impact_targets_by_channel": {"stable": 0},
        "fleet_resilience_min_cost": 3,
        "fleet_recovery_domain_budget": 0,
        "signer_domain_costs": {"hsm-east": 4, "hsm-west": 3, "contractor": 1},
        "log_domain_costs": {"rekor-primary": 2, "rekor-secondary": 3},
        "allowed_cohorts_by_channel": {"stable": ["prod", "canary"], "beta": ["canary"]},
    }
    logs = [
        {"log_id": "rekor-a", "operator_domain": "rekor-primary", "log_secret": "log-a-secret", "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
        {"log_id": "rekor-b", "operator_domain": "rekor-secondary", "log_secret": "log-b-secret", "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
    ]
    signers = [
        {"signer_id": "alice", "trust_domain": "hsm-east", "role": "release", "key_secret": "alice-secret", "artifact_scopes": ["*"], "cohorts": ["prod", "canary"], "predicates": ["build", "scan"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
        {"signer_id": "bob", "trust_domain": "hsm-west", "role": "release", "key_secret": "bob-secret", "artifact_scopes": ["svc-api", "svc-worker"], "cohorts": ["prod"], "predicates": ["build"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
        {"signer_id": "mallory", "trust_domain": "contractor", "role": "observer", "key_secret": "mallory-secret", "artifact_scopes": ["svc-bad"], "cohorts": ["prod"], "predicates": ["build"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
    ]
    artifacts = [
        {"artifact_id": "svc-api", "version": "2.3.0", "digest": "sha256:api", "channel": "stable", "cohort": "prod", "fleet_impact": 5, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-02-01T00:00:00Z", "dependencies": []},
        {"artifact_id": "svc-worker", "version": "1.4.0", "digest": "sha256:worker", "channel": "stable", "cohort": "prod", "fleet_impact": 3, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-02-01T00:00:00Z", "dependencies": []},
        {"artifact_id": "svc-bad", "version": "1.0.0", "digest": "sha256:bad", "channel": "beta", "cohort": "prod", "fleet_impact": 1, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-01-05T00:00:00Z", "dependencies": []},
    ]
    if default_fallback or missing_allowed_cohort_channel:
        policy["allowed_cohorts_by_channel"]["edge"] = ["canary"]
        artifacts.append({"artifact_id": "svc-edge", "version": "3.0", "digest": "sha256:edge", "channel": "edge", "cohort": "canary", "fleet_impact": 2, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-02-01T00:00:00Z", "dependencies": []})
    if multiple_unlisted_channels:
        policy["allowed_cohorts_by_channel"].update({"zeta": ["canary"], "alpha": ["canary"]})
        artifacts.extend([
            {"artifact_id": "a-zeta", "version": "1.0", "digest": "sha256:zeta", "channel": "zeta", "cohort": "canary", "fleet_impact": 1, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-02-01T00:00:00Z", "dependencies": []},
            {"artifact_id": "z-alpha", "version": "1.0", "digest": "sha256:alpha", "channel": "alpha", "cohort": "canary", "fleet_impact": 1, "fleet_dependency_threshold": 0, "rollout_start": "2026-01-01T00:00:00Z", "rollout_end": "2026-02-01T00:00:00Z", "dependencies": []},
        ])
    if dependency_mode == "missing":
        artifacts[1]["dependencies"] = [{"artifact_id": "missing-lib", "min_version": "1.0.0", "allowed_channels": ["stable"], "fleet_weight": 1}]
    elif dependency_mode == "rejected":
        artifacts[1]["dependencies"] = [{"artifact_id": "svc-bad", "min_version": "1.0.0", "allowed_channels": ["beta"], "fleet_weight": 1}]
    elif dependency_mode == "version":
        artifacts[1]["dependencies"] = [{"artifact_id": "svc-api", "min_version": "9.0.0", "allowed_channels": ["stable"], "fleet_weight": 1}]
    elif dependency_mode == "channel":
        artifacts[1]["dependencies"] = [{"artifact_id": "svc-api", "min_version": "1.0.0", "allowed_channels": ["beta"], "fleet_weight": 1}]
    elif dependency_mode == "noncascading":
        artifacts[1]["dependencies"] = [{"artifact_id": "svc-bad", "min_version": "1.0.0", "allowed_channels": ["beta"], "fleet_weight": 1}]
        artifacts[0]["dependencies"] = [{"artifact_id": "svc-worker", "min_version": "1.0.0", "allowed_channels": ["stable"], "fleet_weight": 1}]
    elif dependency_mode == "ordered_blockers":
        artifacts[1]["dependencies"] = [
            {"artifact_id": "missing-first", "min_version": "1.0.0", "allowed_channels": ["stable"], "fleet_weight": 1},
            {"artifact_id": "svc-bad", "min_version": "9.0.0", "allowed_channels": ["stable"], "fleet_weight": 1},
            {"artifact_id": "svc-api", "min_version": "9.0.0", "allowed_channels": ["beta"], "fleet_weight": 1},
            {"artifact_id": "svc-api", "min_version": "1.0.0", "allowed_channels": ["beta"], "fleet_weight": 1},
        ]
    elif dependency_mode == "version_segments":
        artifacts[0]["version"] = "2.3"
        artifacts[1]["dependencies"] = [
            {"artifact_id": "svc-api", "min_version": "2.3.0", "allowed_channels": ["stable"], "fleet_weight": 1},
            {"artifact_id": "svc-api", "min_version": "2.3.0.1", "allowed_channels": ["stable"], "fleet_weight": 1},
        ]

    attestations, inclusions, checkpoints = [], [], []
    add_attestation(attestations, inclusions, checkpoints, artifacts[0], signers[0], logs[0], "build", "att-api-build-a", "cp-api-build-a", sibling="00" * 32)
    add_attestation(attestations, inclusions, checkpoints, artifacts[0], signers[0], logs[1], "scan", "att-api-scan-a", "cp-api-scan-a")
    add_attestation(attestations, inclusions, checkpoints, artifacts[1], signers[1], logs[0], "build", "att-worker-build-b", "cp-worker-build-b")
    add_attestation(attestations, inclusions, checkpoints, artifacts[1], signers[0], logs[1], "scan", "att-worker-scan-a", "cp-worker-scan-a", issued_at="2026-01-09T00:00:01Z")
    bad = add_attestation(attestations, inclusions, checkpoints, artifacts[2], signers[2], logs[0], "build", "att-bad-build", "cp-bad-build")
    bad["digest"] = "sha256:tampered"
    if predicate_threshold_two or predicate_threshold_two_shortfall:
        policy["required_predicates_by_channel"]["stable"]["build"] = 2
    if predicate_threshold_two:
        add_attestation(
            attestations,
            inclusions,
            checkpoints,
            artifacts[0],
            signers[1],
            logs[1],
            "build",
            "att-api-build-b",
            "cp-api-build-b",
        )
    if default_fallback or missing_allowed_cohort_channel:
        add_attestation(attestations, inclusions, checkpoints, artifacts[3], signers[0], logs[0], "build", "att-edge-build-a", "cp-edge-build-a")
    if multiple_unlisted_channels:
        add_attestation(attestations, inclusions, checkpoints, artifacts[-2], signers[0], logs[0], "build", "att-zeta-build", "cp-zeta-build")
        add_attestation(attestations, inclusions, checkpoints, artifacts[-1], signers[0], logs[1], "build", "att-alpha-build", "cp-alpha-build")
    if missing_allowed_cohort_channel:
        policy["allowed_cohorts_by_channel"].pop("edge")
    if bad_proof:
        inclusions[0]["audit_path"][0]["side"] = "left"
    if unknown_signer:
        attestations[2]["signer_id"] = "ghost"
    if unknown_checkpoint:
        attestations[1]["checkpoint_id"] = "cp-missing"
    if checkpoint_log_mismatch:
        checkpoints[3]["log_id"] = "rekor-a"
    if bad_checkpoint_signature:
        checkpoints[2]["signature"] = "0" * 64
    if signer_time_window:
        signers[1]["not_after"] = "2026-01-01T00:00:00Z"
    if bad_signature:
        attestations[2]["signature"] = "0" * 64
    if scope_mismatch:
        signers[0]["artifact_scopes"] = ["unrelated-artifact"]
    if cohort_scope:
        signers[0]["cohorts"] = ["canary"]
    if predicate_scope:
        signers[0]["predicates"] = ["build"]
    if version_mismatch:
        attestations[2]["artifact_version"] = "1.4.1"
    if unknown_log:
        attestations[1]["log_id"] = "untrusted-log"
    if checkpoint_time_window:
        checkpoints[2]["signed_at"] = "2024-12-31T23:59:59Z"
    if checkpoint_after_evaluation:
        checkpoints[2]["signed_at"] = "2026-01-16T00:00:00Z"
    if leaf_hash_mismatch:
        attestations[2]["leaf_hash"] = "0" * 64
    if duplicate_signer:
        add_attestation(
            attestations,
            inclusions,
            checkpoints,
            artifacts[0],
            signers[0],
            logs[1],
            "build",
            "att-api-build-duplicate",
            "cp-api-build-duplicate",
            issued_at="2026-01-10T00:00:00Z",
        )
    if duplicate_signer_tie:
        add_attestation(
            attestations,
            inclusions,
            checkpoints,
            artifacts[0],
            signers[0],
            logs[1],
            "build",
            "att-api-build-0",
            "cp-api-build-tie",
            issued_at="2026-01-09T00:00:00Z",
        )
    if unrequired_predicate:
        signers[0]["predicates"].append("provenance")
        add_attestation(
            attestations,
            inclusions,
            checkpoints,
            artifacts[0],
            signers[0],
            logs[0],
            "provenance",
            "att-api-provenance",
            "cp-api-provenance",
        )
    revocations = []
    if revoked_log:
        revocations.append({"kind": "log", "target_id": "rekor-b", "effective_at": "2026-01-12T00:00:00Z", "reason": "incident"})
    if revoked_signer:
        revocations.append({"kind": "signer", "target_id": "bob", "effective_at": "2026-01-12T00:00:00Z", "reason": "key-leak"})
    if revoked_attestation:
        revocations.append({"kind": "attestation", "target_id": "att-worker-scan-a", "effective_at": "2026-01-12T00:00:00Z", "reason": "bad-scan"})
    if revoked_checkpoint:
        revocations.append({"kind": "checkpoint", "target_id": "cp-api-scan-a", "effective_at": "2026-01-12T00:00:00Z", "reason": "log-rebuild"})
    if future_and_unknown_revocations:
        revocations.extend([
            {"kind": "signer", "target_id": "alice", "effective_at": "2026-01-16T00:00:00Z", "reason": "future-key-event"},
            {"kind": "log", "target_id": "rekor-a", "effective_at": "2026-01-16T00:00:00Z", "reason": "future-log-event"},
            {"kind": "artifact", "target_id": "svc-api", "effective_at": "2026-01-01T00:00:00Z", "reason": "ignored-kind"},
        ])
    if missing_inclusion:
        inclusions = [row for row in inclusions if row["attestation_id"] != "att-api-build-a"]
    if negative_leaf_index:
        inclusions[0]["leaf_index"] = -1
    if out_of_range_leaf_index:
        inclusions[0]["leaf_index"] = checkpoints[0]["tree_size"]
    if invalid_proof_hash:
        inclusions[0]["audit_path"][0]["hash"] = "not-hex"
    if non_lowercase_proof_hash:
        inclusions[0]["audit_path"][0]["hash"] = "AA" * 32
    if invalid_audit_side:
        inclusions[0]["audit_path"][0]["side"] = "above"
    if case_sensitive_ids:
        attestations[2]["signer_id"] = "Bob"
    if inclusive_time_boundaries:
        signers[1]["not_before"] = attestations[2]["issued_at"]
        signers[1]["not_after"] = attestations[2]["issued_at"]
        logs[0]["not_before"] = checkpoints[2]["signed_at"]
        logs[0]["not_after"] = checkpoints[2]["signed_at"]
        artifacts[0]["rollout_start"] = policy["evaluation_time"]
        artifacts[1]["rollout_end"] = policy["evaluation_time"]

    dump_json(path / "policy.json", policy)
    write_jsonl(path / "trusted_logs.jsonl", logs)
    write_jsonl(path / "signers.jsonl", signers)
    write_jsonl(path / "artifacts.jsonl", artifacts)
    write_jsonl(path / "attestations.jsonl", attestations)
    write_jsonl(path / "checkpoints.jsonl", checkpoints)
    write_jsonl(path / "inclusions.jsonl", inclusions)
    write_jsonl(path / "revocations.jsonl", revocations)
    if jsonl_empty_lines:
        for name in [
            "trusted_logs.jsonl",
            "signers.jsonl",
            "artifacts.jsonl",
            "attestations.jsonl",
            "checkpoints.jsonl",
            "inclusions.jsonl",
            "revocations.jsonl",
        ]:
            file_path = path / name
            file_path.write_text("\n" + file_path.read_text().replace("\n", "\n\n"))


def resilience_fixture(path, *, required_cost=6, tie_costs=False, default_fallback=False, invalid_cheap_edge=False):
    base_fixture(path)
    policy = json.loads((path / "policy.json").read_text())
    logs = read_jsonl(path / "trusted_logs.jsonl")
    signers = read_jsonl(path / "signers.jsonl")
    artifacts = read_jsonl(path / "artifacts.jsonl")
    attestations = read_jsonl(path / "attestations.jsonl")
    checkpoints = read_jsonl(path / "checkpoints.jsonl")
    inclusions = read_jsonl(path / "inclusions.jsonl")

    policy["signer_domain_costs"].update({
        "hsm-east": 3 if tie_costs else 1,
        "hsm-north": 3 if tie_costs else 6,
        "hsm-south": 10,
        "hsm-central": 10,
    })
    policy["log_domain_costs"].update({"rekor-primary": 3, "rekor-secondary": 3})
    if default_fallback:
        policy["resilience_min_cost_by_channel"].pop("stable")
        policy["default_resilience_min_cost"] = required_cost
    else:
        policy["resilience_min_cost_by_channel"]["stable"] = required_cost

    extra_signers = [
        {"signer_id": "carol", "trust_domain": "hsm-north", "role": "release", "key_secret": "carol-secret", "artifact_scopes": ["svc-api"], "cohorts": ["prod"], "predicates": ["build"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
        {"signer_id": "dave", "trust_domain": "hsm-south", "role": "release", "key_secret": "dave-secret", "artifact_scopes": ["svc-api"], "cohorts": ["prod"], "predicates": ["scan"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
        {"signer_id": "erin", "trust_domain": "hsm-central", "role": "release", "key_secret": "erin-secret", "artifact_scopes": ["svc-api"], "cohorts": ["prod"], "predicates": ["scan"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"},
    ]
    signers.extend(extra_signers)
    api = artifacts[0]
    add_attestation(attestations, inclusions, checkpoints, api, extra_signers[0], logs[0], "build", "att-api-build-carol-a", "cp-api-build-carol-a")
    add_attestation(attestations, inclusions, checkpoints, api, extra_signers[0], logs[1], "build", "att-api-build-carol-b", "cp-api-build-carol-b")
    add_attestation(attestations, inclusions, checkpoints, api, extra_signers[1], logs[0], "scan", "att-api-scan-dave-a", "cp-api-scan-dave-a")
    add_attestation(attestations, inclusions, checkpoints, api, extra_signers[2], logs[1], "scan", "att-api-scan-erin-b", "cp-api-scan-erin-b")

    if invalid_cheap_edge:
        policy["signer_domain_costs"]["hsm-cheap"] = 1
        policy["log_domain_costs"]["rekor-cheap"] = 1
        cheap_log = {"log_id": "rekor-c", "operator_domain": "rekor-cheap", "log_secret": "log-c-secret", "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
        cheap_signer = {"signer_id": "frank", "trust_domain": "hsm-cheap", "role": "release", "key_secret": "frank-secret", "artifact_scopes": ["svc-api"], "cohorts": ["prod"], "predicates": ["build"], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
        logs.append(cheap_log)
        signers.append(cheap_signer)
        invalid = add_attestation(attestations, inclusions, checkpoints, api, cheap_signer, cheap_log, "build", "att-api-build-frank-c", "cp-api-build-frank-c")
        invalid["signature"] = "0" * 64

    dump_json(path / "policy.json", policy)
    write_jsonl(path / "trusted_logs.jsonl", logs)
    write_jsonl(path / "signers.jsonl", signers)
    write_jsonl(path / "attestations.jsonl", attestations)
    write_jsonl(path / "checkpoints.jsonl", checkpoints)
    write_jsonl(path / "inclusions.jsonl", inclusions)


def fleet_fixture(path, mode="multi_channel"):
    base_fixture(path)
    policy = json.loads((path / "policy.json").read_text())
    logs = read_jsonl(path / "trusted_logs.jsonl")
    signers = read_jsonl(path / "signers.jsonl")
    artifacts = read_jsonl(path / "artifacts.jsonl")
    attestations = read_jsonl(path / "attestations.jsonl")
    checkpoints = read_jsonl(path / "checkpoints.jsonl")
    inclusions = read_jsonl(path / "inclusions.jsonl")

    beta = {
        "artifact_id": "svc-canary",
        "version": "4.1.0",
        "digest": "sha256:canary",
        "channel": "beta",
        "cohort": "canary",
        "fleet_impact": 2,
        "fleet_dependency_threshold": 0,
        "rollout_start": "2026-01-01T00:00:00Z",
        "rollout_end": "2026-02-01T00:00:00Z",
        "dependencies": [],
    }
    artifacts.append(beta)
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        beta,
        signers[0],
        logs[0],
        "build",
        "att-canary-build-a",
        "cp-canary-build-a",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        artifacts[0],
        signers[0],
        logs[1],
        "build",
        "att-api-build-a-secondary",
        "cp-api-build-a-secondary",
        issued_at="2026-01-09T00:00:02Z",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        artifacts[1],
        signers[1],
        logs[1],
        "build",
        "att-worker-build-b-secondary",
        "cp-worker-build-b-secondary",
        issued_at="2026-01-09T00:00:02Z",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        beta,
        signers[0],
        logs[1],
        "build",
        "att-canary-build-a-secondary",
        "cp-canary-build-a-secondary",
        issued_at="2026-01-09T00:00:02Z",
    )
    policy["fleet_resilience_targets_by_channel"] = {"stable": 2, "beta": 1}
    policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 2, "beta": 1}
    policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 8, "beta": 2}
    policy["fleet_resilience_min_cost"] = 4

    if mode == "greedy_trap":
        policy["signer_domain_costs"]["hsm-east"] = 7
        policy["log_domain_costs"].update({"rekor-primary": 2, "rekor-secondary": 2})
    elif mode == "namespace_collision":
        signers[0]["trust_domain"] = "shared"
        logs[1]["operator_domain"] = "shared"
        policy["signer_domain_costs"]["shared"] = 4
        policy["log_domain_costs"]["shared"] = 1
        policy["fleet_resilience_min_cost"] = 3
    elif mode == "impossible":
        policy["fleet_resilience_targets_by_channel"] = {"stable": 3, "beta": 1}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 3, "beta": 1}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 9, "beta": 2}
    elif mode == "zero_targets":
        policy["fleet_resilience_targets_by_channel"] = {"stable": 0, "beta": 0}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 0, "beta": 0}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 0, "beta": 0}
        policy["fleet_resilience_min_cost"] = 1
    elif mode == "strict_shortfall":
        policy["fleet_resilience_min_cost"] = 5
    elif mode == "unusable_cheap":
        cheap_log = {
            "log_id": "rekor-cheap",
            "operator_domain": "log-cheap",
            "log_secret": "log-cheap-secret",
            "not_before": "2025-01-01T00:00:00Z",
            "not_after": "2027-01-01T00:00:00Z",
        }
        cheap_signer = {
            "signer_id": "cheap-signer",
            "trust_domain": "signer-cheap",
            "role": "release",
            "key_secret": "cheap-signer-secret",
            "artifact_scopes": ["svc-api"],
            "cohorts": ["prod"],
            "predicates": ["build"],
            "not_before": "2025-01-01T00:00:00Z",
            "not_after": "2027-01-01T00:00:00Z",
        }
        logs.append(cheap_log)
        signers.append(cheap_signer)
        policy["log_domain_costs"]["log-cheap"] = 1
        policy["signer_domain_costs"]["signer-cheap"] = 1
        bad = add_attestation(
            attestations,
            inclusions,
            checkpoints,
            artifacts[0],
            cheap_signer,
            cheap_log,
            "build",
            "att-api-cheap-invalid",
            "cp-api-cheap-invalid",
        )
        bad["signature"] = "0" * 64
    elif mode == "domain_boundary":
        for idx in range(7):
            extra_log = {
                "log_id": f"boundary-log-{idx}",
                "operator_domain": f"boundary-log-domain-{idx}",
                "log_secret": f"boundary-log-secret-{idx}",
                "not_before": "2025-01-01T00:00:00Z",
                "not_after": "2027-01-01T00:00:00Z",
            }
            artifact = artifacts[idx % 2]
            predicate = "build" if idx % 2 == 0 else "scan"
            extra_signer = {
                "signer_id": f"boundary-signer-{idx}",
                "trust_domain": f"boundary-signer-domain-{idx}",
                "role": "release",
                "key_secret": f"boundary-signer-secret-{idx}",
                "artifact_scopes": [artifact["artifact_id"]],
                "cohorts": ["prod"],
                "predicates": [predicate],
                "not_before": "2025-01-01T00:00:00Z",
                "not_after": "2027-01-01T00:00:00Z",
            }
            logs.append(extra_log)
            signers.append(extra_signer)
            policy["log_domain_costs"][extra_log["operator_domain"]] = idx + 5
            policy["signer_domain_costs"][extra_signer["trust_domain"]] = idx + 6
            add_attestation(
                attestations,
                inclusions,
                checkpoints,
                artifact,
                extra_signer,
                extra_log,
                predicate,
                f"att-boundary-{idx}",
                f"cp-boundary-{idx}",
            )

    dump_json(path / "policy.json", policy)
    rows_by_name = {
        "trusted_logs.jsonl": logs,
        "signers.jsonl": signers,
        "artifacts.jsonl": artifacts,
        "attestations.jsonl": attestations,
        "checkpoints.jsonl": checkpoints,
        "inclusions.jsonl": inclusions,
    }
    for name, rows in rows_by_name.items():
        if mode == "shuffled_rows":
            rows = list(reversed(rows))
        write_jsonl(path / name, rows)


def blast_radius_fixture(path, mode="cascade"):
    fleet_fixture(path)
    policy = json.loads((path / "policy.json").read_text())
    logs = read_jsonl(path / "trusted_logs.jsonl")
    signers = read_jsonl(path / "signers.jsonl")
    artifacts = read_jsonl(path / "artifacts.jsonl")
    attestations = read_jsonl(path / "attestations.jsonl")
    checkpoints = read_jsonl(path / "checkpoints.jsonl")
    inclusions = read_jsonl(path / "inclusions.jsonl")

    tertiary_log = {
        "log_id": "rekor-c",
        "operator_domain": "rekor-tertiary",
        "log_secret": "log-c-secret",
        "not_before": "2025-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
    }
    backup_signer = {
        "signer_id": "carol",
        "trust_domain": "hsm-north",
        "role": "release",
        "key_secret": "carol-secret",
        "artifact_scopes": ["svc-worker", "svc-console"],
        "cohorts": ["prod"],
        "predicates": ["scan"],
        "not_before": "2025-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
    }
    logs.append(tertiary_log)
    signers.append(backup_signer)
    policy["log_domain_costs"]["rekor-tertiary"] = 8
    policy["signer_domain_costs"]["hsm-north"] = 8
    worker = next(row for row in artifacts if row["artifact_id"] == "svc-worker")
    api = next(row for row in artifacts if row["artifact_id"] == "svc-api")
    signers[1]["artifact_scopes"].append("svc-console")
    worker["fleet_dependency_threshold"] = 2
    worker["dependencies"] = [
        {
            "artifact_id": "svc-api",
            "min_version": "2.0.0",
            "allowed_channels": ["stable"],
            "fleet_weight": 2,
        }
    ]
    console = {
        "artifact_id": "svc-console",
        "version": "5.0.0",
        "digest": "sha256:console",
        "channel": "stable",
        "cohort": "prod",
        "fleet_impact": 4,
        "fleet_dependency_threshold": 3,
        "rollout_start": "2026-01-01T00:00:00Z",
        "rollout_end": "2026-02-01T00:00:00Z",
        "dependencies": [
            {
                "artifact_id": "svc-api",
                "min_version": "2.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 1,
            },
            {
                "artifact_id": "svc-worker",
                "min_version": "1.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 2,
            },
        ],
    }
    artifacts.append(console)
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        worker,
        backup_signer,
        tertiary_log,
        "scan",
        "att-worker-scan-carol-c",
        "cp-worker-scan-carol-c",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        console,
        signers[1],
        logs[0],
        "build",
        "att-console-build-b-a",
        "cp-console-build-b-a",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        console,
        signers[1],
        logs[1],
        "build",
        "att-console-build-b-b",
        "cp-console-build-b-b",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        console,
        signers[0],
        logs[1],
        "scan",
        "att-console-scan-alice-b",
        "cp-console-scan-alice-b",
    )
    add_attestation(
        attestations,
        inclusions,
        checkpoints,
        console,
        backup_signer,
        tertiary_log,
        "scan",
        "att-console-scan-carol-c",
        "cp-console-scan-carol-c",
    )

    policy["fleet_resilience_targets_by_channel"] = {"stable": 3}
    policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 1}
    policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 12}
    policy["fleet_resilience_min_cost"] = 3
    policy["fleet_recovery_domain_budget"] = 1
    if mode == "direct_target":
        policy["fleet_recovery_domain_budget"] = 0
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 2}
    elif mode == "impact_target":
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 13}
    elif mode == "cycle":
        policy["fleet_recovery_domain_budget"] = 0
        api["fleet_dependency_threshold"] = 1
        api["dependencies"] = [
            {
                "artifact_id": "svc-console",
                "min_version": "1.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 1,
            }
        ]
    elif mode == "noncandidate_dependency":
        policy["fleet_recovery_domain_budget"] = 0
        worker["fleet_dependency_threshold"] = 1
        worker["dependencies"] = [
            {
                "artifact_id": "svc-bad",
                "min_version": "1.0.0",
                "allowed_channels": ["beta"],
                "fleet_weight": 100,
            }
        ]
        policy["fleet_resilience_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 5}
    elif mode == "insufficient_weight":
        policy["fleet_recovery_domain_budget"] = 0
        worker["dependencies"][0]["fleet_weight"] = 1
        policy["fleet_resilience_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 5}
    elif mode == "duplicate_weights":
        worker["dependencies"] = [
            {
                "artifact_id": "svc-api",
                "min_version": "2.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 1,
            },
            {
                "artifact_id": "svc-api",
                "min_version": "99.0.0",
                "allowed_channels": ["beta"],
                "fleet_weight": 1,
            },
        ]
    elif mode == "zero_threshold":
        policy["fleet_recovery_domain_budget"] = 0
        worker["fleet_dependency_threshold"] = 0
        policy["fleet_resilience_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 5}
    elif mode == "unseeded_cycle":
        policy["fleet_recovery_domain_budget"] = 0
        worker["dependencies"] = [
            {
                "artifact_id": "svc-console",
                "min_version": "1.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 2,
            }
        ]
        console["dependencies"] = [
            {
                "artifact_id": "svc-worker",
                "min_version": "1.0.0",
                "allowed_channels": ["stable"],
                "fleet_weight": 3,
            }
        ]
        policy["fleet_resilience_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 1}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 5}
    elif mode == "recovery_budget_zero":
        policy["fleet_recovery_domain_budget"] = 0
    elif mode == "recovery_budget_two":
        policy["fleet_recovery_domain_budget"] = 2
    elif mode == "margin_witness":
        policy["fleet_resilience_targets_by_channel"] = {"stable": 0}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 0}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 1}
    elif mode == "impossible_direct":
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 4}
    elif mode == "zero_targets":
        policy["fleet_resilience_targets_by_channel"] = {"stable": 0}
        policy["fleet_resilience_direct_targets_by_channel"] = {"stable": 0}
        policy["fleet_resilience_impact_targets_by_channel"] = {"stable": 0}

    dump_json(path / "policy.json", policy)
    rows_by_name = {
        "trusted_logs.jsonl": logs,
        "signers.jsonl": signers,
        "artifacts.jsonl": artifacts,
        "attestations.jsonl": attestations,
        "checkpoints.jsonl": checkpoints,
        "inclusions.jsonl": inclusions,
    }
    for name, rows in rows_by_name.items():
        if mode == "shuffled_rows":
            rows = list(reversed(rows))
        write_jsonl(path / name, rows)


def run_cli(input_dir, output_dir):
    subprocess.run(
        ["cargo", "run", "--release", "--bin", "logseal", "--", str(input_dir), str(output_dir)],
        cwd=PROJECT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    report_path = Path(output_dir) / "report.json"
    assert report_path.exists(), "report.json was not written"
    assert sorted(path.name for path in Path(output_dir).iterdir()) == ["report.json"], "output directory must contain only report.json"
    return json.loads(report_path.read_text())


def assert_case(input_dir, tmp_path, name):
    output_dir = tmp_path / f"out-{name}"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    actual = run_cli(input_dir, output_dir)
    expected = model(input_dir)
    assert actual == expected


def test_public_fixture_exact(tmp_path):
    assert_case(PUBLIC_INPUT, tmp_path, "public")


def test_generated_compatibility_matrix(tmp_path):
    """Exercise ordering, policy fallbacks, dependency blockers, and core evidence failures."""
    cases = [
        {"ordering": "artifact_id"},
        {"ordering": "channel_priority"},
        {"bad_proof": True},
        {"revoked_log": True},
        {"unknown_signer": True},
        {"unknown_checkpoint": True},
        {"checkpoint_log_mismatch": True},
        {"bad_checkpoint_signature": True},
        {"revoked_signer": True},
        {"revoked_attestation": True},
        {"revoked_checkpoint": True},
        {"signer_time_window": True},
        {"default_fallback": True},
        {"dependency_mode": "missing"},
        {"dependency_mode": "rejected"},
        {"dependency_mode": "version"},
        {"dependency_mode": "channel"},
        {"log_quorum_stable": 2},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"case-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"case-{idx}")


def test_documented_signer_and_attestation_failures(tmp_path):
    """Cover signature, signer scope, cohort, predicate, and artifact-version rejection rules."""
    cases = [
        {"bad_signature": True},
        {"scope_mismatch": True},
        {"cohort_scope": True},
        {"predicate_scope": True},
        {"version_mismatch": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"signer-case-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"signer-case-{idx}")


def test_documented_log_checkpoint_and_leaf_failures(tmp_path):
    """Cover unknown logs, checkpoint time boundaries, evaluation cutoff, and leaf mismatch."""
    cases = [
        {"unknown_log": True},
        {"checkpoint_time_window": True},
        {"checkpoint_after_evaluation": True},
        {"leaf_hash_mismatch": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"log-case-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"log-case-{idx}")


def test_documented_inclusion_proof_shape_failures(tmp_path):
    """Cover missing proofs, leaf-index bounds, lowercase hex, and audit-side validation."""
    cases = [
        {"missing_inclusion": True},
        {"negative_leaf_index": True},
        {"out_of_range_leaf_index": True},
        {"invalid_proof_hash": True},
        {"non_lowercase_proof_hash": True},
        {"invalid_audit_side": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"proof-shape-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"proof-shape-{idx}")


def test_duplicate_signers_unrequired_predicates_and_revocation_timing(tmp_path):
    """Cover duplicate signer retention, ignored predicates, future revocations, and unknown kinds."""
    cases = [
        {"duplicate_signer": True},
        {"duplicate_signer_tie": True},
        {"unrequired_predicate": True},
        {"future_and_unknown_revocations": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"policy-edge-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"policy-edge-{idx}")


def test_dependency_phases_blocker_precedence_and_policy_fallbacks(tmp_path):
    """Cover non-cascading dependency state, blocker order, channel fallbacks, and version segments."""
    cases = [
        {"dependency_mode": "noncascading"},
        {"dependency_mode": "ordered_blockers"},
        {"dependency_mode": "version_segments"},
        {"ordering": "channel_priority", "default_fallback": True},
        {"ordering": "channel_priority", "missing_allowed_cohort_channel": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"interaction-case-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"interaction-case-{idx}")


def test_predicate_threshold_requires_distinct_signers(tmp_path):
    """Cover predicate thresholds above one with both distinct-signer success and shortfall."""
    cases = [
        {"predicate_threshold_two": True},
        {"predicate_threshold_two_shortfall": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"predicate-threshold-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"predicate-threshold-{idx}")


def test_input_boundaries_case_sensitivity_and_unlisted_channel_order(tmp_path):
    """Cover blank JSONL lines, case-sensitive ids, inclusive windows, and unlisted channels."""
    cases = [
        {"jsonl_empty_lines": True},
        {"case_sensitive_ids": True},
        {"inclusive_time_boundaries": True},
        {"ordering": "channel_priority", "multiple_unlisted_channels": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"input-boundary-{idx}"
        base_fixture(input_dir, **kwargs)
        assert_case(input_dir, tmp_path, f"input-boundary-{idx}")


def test_unknown_object_gating_and_additive_log_failures(tmp_path):
    """Keep each log/checkpoint check active whenever its own required objects exist."""
    gated_dir = tmp_path / "gated-unknowns"
    base_fixture(gated_dir, unknown_log=True, unknown_checkpoint=True)
    gated = run_cli(gated_dir, tmp_path / "out-gated-unknowns")
    assert gated == model(gated_dir)
    api = next(row for row in gated["artifacts"] if row["artifact_id"] == "svc-api")
    assert "unknown_log" in api["reasons"] and "unknown_checkpoint" in api["reasons"]
    assert not ({"checkpoint_log_mismatch", "checkpoint_time_window", "checkpoint_after_evaluation"} & set(api["reasons"]))

    unknown_log_dir = tmp_path / "unknown-log-existing-checkpoint"
    base_fixture(unknown_log_dir, unknown_log=True)
    unknown_log_atts = read_jsonl(unknown_log_dir / "attestations.jsonl")
    next(row for row in unknown_log_atts if row["attestation_id"] == "att-api-scan-a")["leaf_hash"] = "0" * 64
    write_jsonl(unknown_log_dir / "attestations.jsonl", unknown_log_atts)
    unknown_log_checkpoints = read_jsonl(unknown_log_dir / "checkpoints.jsonl")
    next(row for row in unknown_log_checkpoints if row["checkpoint_id"] == "cp-api-scan-a")["signed_at"] = "2026-01-16T00:00:00Z"
    write_jsonl(unknown_log_dir / "checkpoints.jsonl", unknown_log_checkpoints)
    write_jsonl(
        unknown_log_dir / "revocations.jsonl",
        [
            {"kind": "log", "target_id": "untrusted-log", "effective_at": "2026-01-12T00:00:00Z", "reason": "retired"},
            {"kind": "checkpoint", "target_id": "cp-api-scan-a", "effective_at": "2026-01-12T00:00:00Z", "reason": "superseded"},
        ],
    )
    unknown_log_report = run_cli(unknown_log_dir, tmp_path / "out-unknown-log-existing-checkpoint")
    assert unknown_log_report == model(unknown_log_dir)
    api = next(row for row in unknown_log_report["artifacts"] if row["artifact_id"] == "svc-api")
    assert {
        "unknown_log",
        "checkpoint_log_mismatch",
        "checkpoint_after_evaluation",
        "revoked_log",
        "revoked_checkpoint",
        "leaf_hash_mismatch",
        "bad_inclusion_proof",
    } <= set(api["reasons"])
    assert not ({"bad_checkpoint_signature", "checkpoint_time_window"} & set(api["reasons"]))

    missing_checkpoint_dir = tmp_path / "known-revoked-log-missing-checkpoint"
    base_fixture(missing_checkpoint_dir, unknown_checkpoint=True, revoked_log=True)
    missing_checkpoint_report = run_cli(missing_checkpoint_dir, tmp_path / "out-known-revoked-log-missing-checkpoint")
    assert missing_checkpoint_report == model(missing_checkpoint_dir)
    api = next(row for row in missing_checkpoint_report["artifacts"] if row["artifact_id"] == "svc-api")
    assert {"unknown_checkpoint", "revoked_log"} <= set(api["reasons"])
    assert not (
        {
            "checkpoint_log_mismatch",
            "bad_checkpoint_signature",
            "checkpoint_time_window",
            "checkpoint_after_evaluation",
            "revoked_checkpoint",
            "leaf_hash_mismatch",
            "bad_inclusion_proof",
        }
        & set(api["reasons"])
    )

    additive_dir = tmp_path / "additive-log-failures"
    base_fixture(
        additive_dir,
        bad_proof=True,
        bad_checkpoint_signature=True,
        checkpoint_after_evaluation=True,
        revoked_log=True,
        revoked_checkpoint=True,
        leaf_hash_mismatch=True,
    )
    additive = run_cli(additive_dir, tmp_path / "out-additive-log-failures")
    assert additive == model(additive_dir)
    emitted = {reason for row in additive["artifacts"] for reason in row["reasons"]}
    assert {
        "bad_checkpoint_signature",
        "checkpoint_after_evaluation",
        "revoked_log",
        "revoked_checkpoint",
        "leaf_hash_mismatch",
        "bad_inclusion_proof",
    } <= emitted


def test_weighted_resilience_cut_defeats_greedy_domain_removal(tmp_path):
    """Require the globally minimum joint signer/log cut and the strict cost boundary."""
    for required_cost, shortfall in [(6, False), (7, True)]:
        input_dir = tmp_path / f"weighted-cut-{required_cost}"
        resilience_fixture(input_dir, required_cost=required_cost)
        report = run_cli(input_dir, tmp_path / f"out-weighted-cut-{required_cost}")
        assert report == model(input_dir)
        api = next(row for row in report["artifacts"] if row["artifact_id"] == "svc-api")
        assert api["resilience_cut"] == {
            "cost": 6,
            "failure": "threshold:build",
            "signer_domains": [],
            "log_domains": ["rekor-primary", "rekor-secondary"],
        }
        assert ("resilience_shortfall" in api["reasons"]) is shortfall


def test_resilience_ties_fallbacks_and_unusable_edges(tmp_path):
    """Cover complete-cut tie-breaking, default policy fallback, and unusable evidence exclusion."""
    cases = [
        {"tie_costs": True},
        {"default_fallback": True},
        {"invalid_cheap_edge": True},
    ]
    for idx, kwargs in enumerate(cases):
        input_dir = tmp_path / f"resilience-detail-{idx}"
        resilience_fixture(input_dir, **kwargs)
        report = run_cli(input_dir, tmp_path / f"out-resilience-detail-{idx}")
        assert report == model(input_dir)
        api = next(row for row in report["artifacts"] if row["artifact_id"] == "svc-api")
        assert api["resilience_cut"]["cost"] == 6
        assert api["resilience_cut"]["signer_domains"] == []
        assert api["resilience_cut"]["log_domains"] == ["rekor-primary", "rekor-secondary"]
        if kwargs.get("invalid_cheap_edge"):
            assert "bad_signature" in api["reasons"]
            assert "hsm-cheap" not in api["resilience_cut"]["signer_domains"]
            assert "rekor-cheap" not in api["resilience_cut"]["log_domains"]


def test_resilience_empty_cut_and_no_possible_cut(tmp_path):
    """Distinguish a zero-cost baseline failure from a policy with no positive requirement."""
    baseline = tmp_path / "baseline-empty-cut"
    base_fixture(baseline)
    baseline_report = run_cli(baseline, tmp_path / "out-baseline-empty-cut")
    assert baseline_report == model(baseline)
    bad = next(row for row in baseline_report["artifacts"] if row["artifact_id"] == "svc-bad")
    assert bad["resilience_cut"] == {
        "cost": 0,
        "failure": "threshold:build",
        "signer_domains": [],
        "log_domains": [],
    }
    assert "resilience_shortfall" in bad["reasons"]

    no_cut = tmp_path / "no-cut"
    base_fixture(no_cut)
    policy = json.loads((no_cut / "policy.json").read_text())
    policy["required_predicates_by_channel"]["stable"] = {}
    policy["log_quorum_by_channel"]["stable"] = 0
    policy["resilience_min_cost_by_channel"]["stable"] = 100
    dump_json(no_cut / "policy.json", policy)
    no_cut_report = run_cli(no_cut, tmp_path / "out-no-cut")
    assert no_cut_report == model(no_cut)
    api = next(row for row in no_cut_report["artifacts"] if row["artifact_id"] == "svc-api")
    assert api["resilience_cut"] == {
        "cost": None,
        "failure": None,
        "signer_domains": [],
        "log_domains": [],
    }
    assert "resilience_shortfall" not in api["reasons"]


def test_fleet_resilience_global_targets_ties_and_boundaries(tmp_path):
    """Require one canonical cross-artifact domain cut across all targeted channels."""
    modes = [
        "multi_channel",
        "greedy_trap",
        "namespace_collision",
        "impossible",
        "zero_targets",
        "strict_shortfall",
        "unusable_cheap",
        "shuffled_rows",
        "domain_boundary",
    ]
    for mode in modes:
        input_dir = tmp_path / f"fleet-{mode}"
        fleet_fixture(input_dir, mode)
        report = run_cli(input_dir, tmp_path / f"out-fleet-{mode}")
        assert report == model(input_dir)
        cut = report["fleet_resilience_cut"]
        if mode == "multi_channel":
            assert cut == {
                "cost": 4,
                "shortfall": False,
                "directly_broken_artifacts": ["svc-api", "svc-canary", "svc-worker"],
                "broken_artifacts": ["svc-api", "svc-canary", "svc-worker"],
                "cascade_depth_by_artifact": {"svc-api": 0, "svc-canary": 0, "svc-worker": 0},
                "broken_impact_by_channel": {"stable": 8, "beta": 2},
                "signer_domains": ["hsm-east"],
                "log_domains": [],
                "recovery_breakpoint": {
                    "count": 1,
                    "cost": 4,
                    "signer_domains": ["hsm-east"],
                    "log_domains": [],
                },
                "recovery_margin": {
                    "value": 0,
                    "restored_cost": 0,
                    "signer_domains": [],
                    "log_domains": [],
                },
            }
        elif mode == "greedy_trap":
            assert cut["cost"] == 4 and cut["log_domains"] == ["rekor-primary", "rekor-secondary"]
        elif mode == "namespace_collision":
            assert cut["cost"] == 3 and cut["signer_domains"] == []
            assert cut["log_domains"] == ["rekor-primary", "shared"]
        elif mode == "impossible":
            assert cut["cost"] is None and cut["broken_artifacts"] == [] and cut["shortfall"] is False
        elif mode == "zero_targets":
            assert cut["cost"] == 0 and cut["shortfall"] is True
            assert cut["directly_broken_artifacts"] == [] and cut["broken_artifacts"] == []
            assert cut["cascade_depth_by_artifact"] == {}
            assert cut["broken_impact_by_channel"] == {"stable": 0, "beta": 0}
            assert cut["signer_domains"] == [] and cut["log_domains"] == []
        elif mode == "strict_shortfall":
            assert cut["cost"] == 4 and cut["shortfall"] is True
        elif mode == "unusable_cheap":
            assert "signer-cheap" not in cut["signer_domains"] and "log-cheap" not in cut["log_domains"]


def test_weighted_dependency_amplified_fleet_blast_radius_and_round_depths(tmp_path):
    """Require recovery-safe cuts, weighted synchronous rounds, depths, and all target families."""
    modes = [
        "cascade",
        "direct_target",
        "impact_target",
        "cycle",
        "noncandidate_dependency",
        "insufficient_weight",
        "duplicate_weights",
        "zero_threshold",
        "unseeded_cycle",
        "recovery_budget_zero",
        "recovery_budget_two",
        "margin_witness",
        "impossible_direct",
        "zero_targets",
        "shuffled_rows",
    ]
    reports = {}
    for mode in modes:
        input_dir = tmp_path / f"blast-{mode}"
        blast_radius_fixture(input_dir, mode)
        report = run_cli(input_dir, tmp_path / f"out-blast-{mode}")
        assert report == model(input_dir)
        reports[mode] = report["fleet_resilience_cut"]

    cascade = reports["cascade"]
    assert cascade["cost"] == 7
    assert cascade["directly_broken_artifacts"] == ["svc-api"]
    assert cascade["broken_artifacts"] == ["svc-api", "svc-console", "svc-worker"]
    assert cascade["cascade_depth_by_artifact"] == {"svc-api": 0, "svc-console": 2, "svc-worker": 1}
    assert cascade["broken_impact_by_channel"] == {"stable": 12}
    assert cascade["signer_domains"] == ["hsm-east"]
    assert cascade["log_domains"] == ["rekor-secondary"]
    assert cascade["recovery_breakpoint"] == {
        "count": 2,
        "cost": 7,
        "signer_domains": ["hsm-east"],
        "log_domains": ["rekor-secondary"],
    }
    assert cascade["recovery_margin"] == {
        "value": 0,
        "restored_cost": 0,
        "signer_domains": [],
        "log_domains": [],
    }
    assert reports["direct_target"]["cost"] == 5
    assert reports["direct_target"]["directly_broken_artifacts"] == ["svc-api", "svc-console", "svc-worker"]
    assert reports["cycle"]["cascade_depth_by_artifact"] == cascade["cascade_depth_by_artifact"]
    assert reports["duplicate_weights"] == cascade
    assert reports["impact_target"]["cost"] is None
    assert reports["recovery_budget_zero"]["cost"] == 3
    assert reports["recovery_budget_zero"]["signer_domains"] == []
    assert reports["recovery_budget_two"]["cost"] is None
    assert reports["margin_witness"]["recovery_margin"] == {
        "value": 1,
        "restored_cost": 3,
        "signer_domains": ["hsm-west"],
        "log_domains": [],
    }
    assert reports["margin_witness"]["recovery_breakpoint"] == {
        "count": 2,
        "cost": 6,
        "signer_domains": ["hsm-west"],
        "log_domains": ["rekor-secondary"],
    }
    assert reports["impossible_direct"]["cost"] is None
    for mode in ["noncandidate_dependency", "insufficient_weight", "zero_threshold", "unseeded_cycle"]:
        assert reports[mode]["cost"] == 3
        assert reports[mode]["broken_artifacts"] == ["svc-console", "svc-worker"]
        assert reports[mode]["directly_broken_artifacts"] == ["svc-console", "svc-worker"]
        assert reports[mode]["cascade_depth_by_artifact"] == {"svc-console": 0, "svc-worker": 0}
    assert reports["zero_targets"]["directly_broken_artifacts"] == []
    assert reports["zero_targets"]["cascade_depth_by_artifact"] == {}
    assert reports["shuffled_rows"] == cascade


def test_output_is_regenerated_from_clean_directory(tmp_path):
    """Require every invocation to replace stale report content without creating extra files."""
    input_dir = tmp_path / "rerun"
    base_fixture(input_dir, dependency_mode="channel")
    out = tmp_path / "out-rerun"
    out.mkdir()
    (out / "report.json").write_text("{}")
    actual = run_cli(input_dir, out)
    assert actual == model(input_dir)


def test_report_schema_and_required_empty_values(tmp_path):
    """Validate exact report keys and required empty collections."""
    input_dir = tmp_path / "schema"
    base_fixture(input_dir, revoked_log=True)
    report = run_cli(input_dir, tmp_path / "out-schema")
    assert set(report) == {"generated_at", "artifacts", "fleet_resilience_cut", "summary"}
    assert set(report["fleet_resilience_cut"]) == {
        "cost",
        "shortfall",
        "directly_broken_artifacts",
        "broken_artifacts",
        "cascade_depth_by_artifact",
        "broken_impact_by_channel",
        "signer_domains",
        "log_domains",
        "recovery_breakpoint",
        "recovery_margin",
    }
    assert report["summary"]["total"] == len(report["artifacts"])
    for row in report["artifacts"]:
        assert set(row) == {
            "artifact_id",
            "version",
            "channel",
            "cohort",
            "status",
            "reasons",
            "accepted_signers",
            "accepted_logs",
            "resilience_cut",
            "dependency_blockers",
        }
        assert isinstance(row["accepted_logs"], list)
        assert isinstance(row["dependency_blockers"], list)
        assert isinstance(row["accepted_signers"], dict)
        assert set(row["resilience_cut"]) == {"cost", "failure", "signer_domains", "log_domains"}
