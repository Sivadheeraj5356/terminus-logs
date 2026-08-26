import hashlib
import json
import os
import subprocess
from itertools import combinations
from pathlib import Path


APP = Path("/app")
PUBLIC_BUNDLE = APP / "containment" / "bundle.json"
PUBLIC_SHA256 = "748d8453a6bb6e073ee3830b7771f45a386928d110f28e1aaea0f8326aea391d"


def parse_time(text):
    if text is None:
        return None
    return text.replace("Z", "+00:00")


def starts_with_any(values, prefixes):
    return any(value.startswith(prefix) for value in values for prefix in prefixes)


def lex_less(left, right):
    return tuple(left) < tuple(right)


def plan_summary(plan, policy):
    confidence = {}
    owners = set()
    review = outage = slots = 0
    action_ids = []
    for action in plan:
        action_ids.append(action["action_id"])
        owners.add(action["owner"])
        review += action["review_minutes"]
        outage += action["outage_units"]
        slots += action["rule_slots"]
        family_confidence = action.get("family_confidence", {})
        for family in action["families"]:
            confidence[family] = confidence.get(family, 0) + family_confidence.get(family, 100)
        for family, amount in family_confidence.items():
            if family not in action["families"]:
                confidence[family] = confidence.get(family, 0) + amount
    covered = {
        family
        for family, amount in confidence.items()
        if amount >= policy.get("family_min_confidence", {}).get(family, 1)
    }
    return {
        "selected_actions": sorted(action_ids),
        "risk_score": sum(policy["family_scores"][family] for family in covered),
        "review_minutes": review,
        "outage_units": outage,
        "rule_slots": slots,
        "selected_owners": sorted(owners),
    }


def better_plan(left, right, policy):
    if right is None:
        return True
    a = plan_summary(left, policy)
    b = plan_summary(right, policy)
    if policy["tie_mode"] == "risk_then_cost":
        keys = [
            (a["risk_score"], b["risk_score"], True),
            (a["outage_units"], b["outage_units"], False),
            (a["review_minutes"], b["review_minutes"], False),
            (a["rule_slots"], b["rule_slots"], False),
            (len(a["selected_actions"]), len(b["selected_actions"]), False),
        ]
    else:
        keys = [
            (a["outage_units"], b["outage_units"], False),
            (a["review_minutes"], b["review_minutes"], False),
            (a["rule_slots"], b["rule_slots"], False),
            (a["risk_score"], b["risk_score"], True),
            (len(a["selected_actions"]), len(b["selected_actions"]), False),
        ]
    for left_value, right_value, higher in keys:
        if left_value != right_value:
            return left_value > right_value if higher else left_value < right_value
    return lex_less(a["selected_actions"], b["selected_actions"])


def usable(action, asset, policy):
    if action["asset_id"] != asset["asset_id"]:
        return False
    now = parse_time(policy["evaluation_time"])
    if parse_time(action["valid_from"]) > now:
        return False
    expires = parse_time(action["expires_at"])
    if expires is not None and not (now < expires):
        return False
    if action["allowed_zones"] and asset["zone"] not in action["allowed_zones"]:
        return False
    if starts_with_any(asset["tags"], action["blocked_tag_prefixes"]):
        return False
    if any(family not in policy["family_scores"] for family in action["families"]):
        return False
    if any(family not in policy["family_scores"] for family in action.get("family_confidence", {})):
        return False
    return action["owner"] in policy["allowed_owners"]


def valid_plan(plan, policy, asset):
    seen_types = set()
    selected_ids = {action["action_id"] for action in plan}
    confidence = {}
    owners = set()
    owner_review = {}
    owner_count = {}
    review = outage = slots = 0
    blast_radius = 0
    for action in plan:
        if action["action_type"] in seen_types:
            return False
        seen_types.add(action["action_type"])
        if selected_ids.intersection(action["conflicts_with"]):
            return False
        for group in action.get("requires_any", []):
            if not group or not selected_ids.intersection(group):
                return False
        for required_type in action.get("requires_all_action_types", []):
            if required_type not in seen_types and not any(other["action_type"] == required_type for other in plan):
                return False
        family_confidence = action.get("family_confidence", {})
        for family in action["families"]:
            confidence[family] = confidence.get(family, 0) + family_confidence.get(family, 100)
        for family, amount in family_confidence.items():
            if family not in action["families"]:
                confidence[family] = confidence.get(family, 0) + amount
        owners.add(action["owner"])
        owner_review[action["owner"]] = owner_review.get(action["owner"], 0) + action["review_minutes"]
        owner_count[action["owner"]] = owner_count.get(action["owner"], 0) + 1
        review += action["review_minutes"]
        outage += action["outage_units"]
        slots += action["rule_slots"]
        blast_radius += action.get("blast_radius", 0)
    if not plan and (policy["threshold"] > 0 or policy["required_families"]):
        return False
    covered = {
        family
        for family, amount in confidence.items()
        if amount >= policy.get("family_min_confidence", {}).get(family, 1)
    }
    if any(family not in covered for family in policy["required_families"]):
        return False
    if sum(policy["family_scores"][family] for family in covered) < policy["threshold"]:
        return False
    if review > policy["review_budget"] or outage > policy["outage_budget"]:
        return False
    if slots > policy["rule_slot_budget"]:
        return False
    if len(owners) < policy["min_distinct_owners"]:
        return False
    for owner, cap in policy.get("owner_review_caps", {}).items():
        if owner_review.get(owner, 0) > cap:
            return False
    max_actions = policy.get("max_actions_per_owner", 0)
    if max_actions and any(count > max_actions for count in owner_count.values()):
        return False
    zone_cap = policy.get("zone_blast_radius_budget", {}).get(asset["zone"])
    if zone_cap is not None and blast_radius > zone_cap:
        return False
    if outage > policy["escalation_outage_threshold"]:
        return any(action["action_type"] == "management_approval" for action in plan)
    return True


def canonical_plan(asset, bundle):
    policy = bundle["policy"]
    candidates = [action for action in bundle["actions"] if usable(action, asset, policy)]
    best = [] if not policy["required_families"] and policy["threshold"] == 0 else None
    for size in range(1, len(candidates) + 1):
        for plan in combinations(candidates, size):
            plan = list(plan)
            if valid_plan(plan, policy, asset) and better_plan(plan, best, policy):
                best = plan
    return best


def better_asset(left, right, bundle, plans):
    if right is None:
        return True
    policy = bundle["policy"]
    left_plan = plans[left["asset_id"]]
    right_plan = plans[right["asset_id"]]
    if better_plan(left_plan, right_plan, policy):
        return True
    if better_plan(right_plan, left_plan, policy):
        return False
    if left["criticality"] != right["criticality"]:
        return left["criticality"] > right["criticality"]
    if parse_time(left["detected_at"]) != parse_time(right["detected_at"]):
        return parse_time(left["detected_at"]) > parse_time(right["detected_at"])
    return left["asset_id"] < right["asset_id"]


def expected(bundle):
    policy = bundle["policy"]
    plans = {}
    blocked = set()
    winner = None
    for asset in bundle["assets"]:
        if starts_with_any(asset["tags"], policy["deny_tag_prefixes"]):
            blocked.add(asset["asset_id"])
            plans[asset["asset_id"]] = None
            continue
        plans[asset["asset_id"]] = canonical_plan(asset, bundle)
        if plans[asset["asset_id"]] is not None and better_asset(asset, winner, bundle, plans):
            winner = asset
    if winner is None:
        top = {
            "status": "rejected",
            "winner": None,
            "selected_actions": [],
            "risk_score": 0,
            "review_minutes": 0,
            "outage_units": 0,
            "rule_slots": 0,
            "selected_owners": [],
        }
    else:
        top = {"status": "accepted", "winner": winner["asset_id"], **plan_summary(plans[winner["asset_id"]], policy)}
    rows = []
    for asset in bundle["assets"]:
        plan = plans[asset["asset_id"]]
        if plan is None:
            summary = {
                "selected_actions": [],
                "risk_score": 0,
                "review_minutes": 0,
                "outage_units": 0,
                "rule_slots": 0,
                "selected_owners": [],
            }
        else:
            summary = plan_summary(plan, policy)
        reasons = []
        if asset["asset_id"] in blocked:
            reasons.append("blocked_tag")
        elif plan is None:
            reasons.append("no_valid_plan")
        elif winner is None or asset["asset_id"] != winner["asset_id"]:
            reasons.append("not_selected")
        rows.append(
            {
                "asset_id": asset["asset_id"],
                "status": "accepted" if winner is not None and asset["asset_id"] == winner["asset_id"] else "rejected",
                **summary,
                "reasons": reasons,
            }
        )
    return {**top, "assets": rows}


def run_cli(bundle, tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle_path = tmp_path / "bundle.json"
    out_path = tmp_path / "decision.json"
    bundle_path.write_text(json.dumps(bundle, separators=(",", ":"), sort_keys=True))
    subprocess.run(["go", "build", "-o", str(APP / "quarantine-plan"), str(APP)], cwd=APP, check=True, timeout=30)
    subprocess.run(
        [str(APP / "quarantine-plan"), "--bundle", str(bundle_path), "--out", str(out_path)],
        cwd=APP,
        check=True,
        timeout=12,
    )
    assert out_path.exists(), "CLI did not write the requested output path"
    return json.loads(out_path.read_text())


def assert_exact_schema(doc):
    assert list(doc.keys()) == [
        "status",
        "winner",
        "selected_actions",
        "risk_score",
        "review_minutes",
        "outage_units",
        "rule_slots",
        "selected_owners",
        "assets",
    ]
    for row in doc["assets"]:
        assert list(row.keys()) == [
            "asset_id",
            "status",
            "selected_actions",
            "risk_score",
            "review_minutes",
            "outage_units",
            "rule_slots",
            "selected_owners",
            "reasons",
        ]


def base_bundle(tie_mode="risk_then_cost"):
    return {
        "policy": {
            "evaluation_time": "2026-05-17T13:00:00Z",
            "required_families": ["malware", "c2", "credential"],
            "family_scores": {"malware": 5, "c2": 4, "credential": 3, "lateral": 2, "persistence": 2, "exfil": 4},
            "family_min_confidence": {"malware": 90, "c2": 80, "credential": 90, "lateral": 50, "persistence": 50, "exfil": 70},
            "threshold": 12,
            "review_budget": 9,
            "outage_budget": 7,
            "rule_slot_budget": 5,
            "min_distinct_owners": 3,
            "deny_tag_prefixes": ["lab:", "decommissioned:"],
            "allowed_owners": ["edr", "netops", "identity", "soc-lead", "dns", "cloud"],
            "owner_review_caps": {"soc-lead": 4, "netops": 3},
            "max_actions_per_owner": 1,
            "zone_blast_radius_budget": {"prod": 8, "corp": 5},
            "escalation_outage_threshold": 5,
            "tie_mode": tie_mode,
        },
        "assets": [],
        "actions": [],
    }


def add_asset(bundle, asset_id, criticality=5, zone="prod", tags=None, detected_at="2026-05-17T12:00:00Z"):
    bundle["assets"].append(
        {"asset_id": asset_id, "zone": zone, "criticality": criticality, "detected_at": detected_at, "tags": tags or ["tier:web"]}
    )


def add_action(bundle, action_id, asset_id, action_type, families, owner, review, outage, slots, **kw):
    action = {
        "action_id": action_id,
        "asset_id": asset_id,
        "action_type": action_type,
        "families": families,
        "owner": owner,
        "review_minutes": review,
        "outage_units": outage,
        "rule_slots": slots,
        "valid_from": kw.get("valid_from", "2026-05-17T11:00:00Z"),
        "expires_at": kw.get("expires_at"),
        "allowed_zones": kw.get("allowed_zones", ["prod"]),
        "blocked_tag_prefixes": kw.get("blocked_tag_prefixes", []),
        "conflicts_with": kw.get("conflicts_with", []),
        "family_confidence": kw.get("family_confidence", {family: 100 for family in families}),
        "requires_any": kw.get("requires_any", []),
        "requires_all_action_types": kw.get("requires_all_action_types", []),
        "blast_radius": kw.get("blast_radius", 0),
    }
    bundle["actions"].append(action)


def public_bundle():
    return json.loads(PUBLIC_BUNDLE.read_text())


def variant_balanced_vs_broad(tie_mode="risk_then_cost"):
    b = base_bundle(tie_mode)
    add_asset(b, "host-zeta", criticality=6)
    add_action(b, "broad", "host-zeta", "isolate_vlan", ["malware", "c2", "credential", "lateral"], "netops", 3, 6, 2)
    add_action(b, "mgr", "host-zeta", "management_approval", [], "soc-lead", 4, 0, 0, allowed_zones=[])
    add_action(b, "dns", "host-zeta", "dns_sinkhole", ["c2"], "dns", 1, 1, 1)
    add_action(b, "edr", "host-zeta", "edr_kill", ["malware", "persistence"], "edr", 2, 1, 1)
    add_action(b, "id", "host-zeta", "disable_user", ["credential"], "identity", 2, 1, 1, allowed_zones=[])
    return b


def variant_conflict_and_one_type():
    b = base_bundle()
    add_asset(b, "host-eta", criticality=8)
    add_action(b, "dns-a", "host-eta", "dns_sinkhole", ["c2", "exfil"], "dns", 2, 1, 1)
    add_action(b, "dns-b", "host-eta", "dns_sinkhole", ["c2"], "cloud", 1, 1, 1)
    add_action(b, "edr", "host-eta", "edr_kill", ["malware"], "edr", 2, 1, 1, conflicts_with=["id"])
    add_action(b, "id", "host-eta", "disable_user", ["credential"], "identity", 2, 1, 1)
    add_action(b, "hostfw", "host-eta", "host_firewall", ["malware", "credential"], "cloud", 3, 1, 2)
    return b


def variant_asset_tiebreak():
    b = variant_balanced_vs_broad("cost_then_risk")
    b["assets"][0]["criticality"] = 4
    add_asset(b, "host-theta", criticality=9, detected_at="2026-05-17T12:30:00Z")
    for base in [
        ("theta-dns", "dns_sinkhole", ["c2"], "dns", 1, 1, 1),
        ("theta-edr", "edr_kill", ["malware"], "edr", 2, 1, 1),
        ("theta-id", "disable_user", ["credential"], "identity", 2, 1, 1),
    ]:
        add_action(b, base[0], "host-theta", base[1], base[2], base[3], base[4], base[5], base[6], allowed_zones=[] if base[1] == "disable_user" else ["prod"])
    return b


def variant_no_winner():
    b = base_bundle()
    add_asset(b, "host-iota", criticality=3)
    add_action(b, "only-edr", "host-iota", "edr_kill", ["malware"], "edr", 1, 1, 1)
    return b


def variant_confidence_dependencies():
    b = base_bundle("risk_then_cost")
    b["policy"]["threshold"] = 14
    b["policy"]["review_budget"] = 10
    b["policy"]["rule_slot_budget"] = 6
    add_asset(b, "host-kappa", criticality=8)
    add_action(
        b,
        "k-edr-light",
        "host-kappa",
        "edr_kill",
        ["malware", "persistence"],
        "edr",
        2,
        1,
        1,
        family_confidence={"malware": 60, "persistence": 70},
    )
    add_action(
        b,
        "k-hostfw",
        "host-kappa",
        "host_firewall",
        ["malware", "credential"],
        "cloud",
        2,
        1,
        2,
        family_confidence={"malware": 35, "credential": 45},
        requires_any=[["k-edr-light", "missing-action"]],
    )
    add_action(
        b,
        "k-id",
        "host-kappa",
        "disable_user",
        ["credential"],
        "identity",
        2,
        1,
        1,
        allowed_zones=[],
        family_confidence={"credential": 50},
        requires_all_action_types=["edr_kill"],
    )
    add_action(b, "k-dns", "host-kappa", "dns_sinkhole", ["c2"], "dns", 1, 1, 1, family_confidence={"c2": 85})
    add_action(b, "k-cloud-extra", "host-kappa", "cloud_sg_block", ["exfil", "c2"], "cloud", 3, 2, 2, family_confidence={"exfil": 75, "c2": 20})
    add_action(b, "k-bad-shortcut", "host-kappa", "isolate_vlan", ["malware", "c2", "credential", "exfil"], "netops", 3, 5, 2, family_confidence={"malware": 100, "c2": 100, "credential": 100, "exfil": 100}, requires_any=[[]])
    return b


def variant_owner_and_blast_caps():
    b = base_bundle("cost_then_risk")
    b["policy"]["threshold"] = 12
    b["policy"]["review_budget"] = 12
    b["policy"]["zone_blast_radius_budget"]["prod"] = 4
    b["policy"]["max_actions_per_owner"] = 2
    add_asset(b, "host-lambda", criticality=7)
    add_action(b, "l-edr", "host-lambda", "edr_kill", ["malware"], "edr", 2, 1, 1, blast_radius=1)
    add_action(b, "l-edr-follow", "host-lambda", "memory_scrub", ["persistence"], "edr", 2, 1, 1, blast_radius=1)
    add_action(b, "l-dns", "host-lambda", "dns_sinkhole", ["c2"], "dns", 1, 1, 1, blast_radius=1)
    add_action(b, "l-id", "host-lambda", "disable_user", ["credential"], "identity", 2, 1, 1, allowed_zones=[], blast_radius=1)
    add_action(b, "l-cloud-wide", "host-lambda", "cloud_sg_block", ["exfil", "c2"], "cloud", 2, 1, 1, blast_radius=5)
    add_action(b, "l-net-wide", "host-lambda", "isolate_vlan", ["malware", "c2", "credential", "exfil"], "netops", 3, 2, 2, blast_radius=5)
    return b


def variant_large_branching():
    b = base_bundle("risk_then_cost")
    b["policy"]["required_families"] = ["malware", "c2", "credential", "exfil"]
    b["policy"]["threshold"] = 16
    b["policy"]["review_budget"] = 9
    b["policy"]["outage_budget"] = 6
    b["policy"]["rule_slot_budget"] = 7
    b["policy"]["min_distinct_owners"] = 4
    b["policy"]["max_actions_per_owner"] = 2
    b["policy"]["zone_blast_radius_budget"]["prod"] = 7
    add_asset(b, "host-omega", criticality=10, detected_at="2026-05-17T12:55:00Z")

    add_action(b, "omega-edr-core", "host-omega", "edr_kill", ["malware", "persistence"], "edr", 2, 1, 1, blast_radius=1)
    add_action(b, "omega-dns-core", "host-omega", "dns_sinkhole", ["c2", "lateral"], "dns", 1, 1, 1, blast_radius=1)
    add_action(b, "omega-id-core", "host-omega", "disable_user", ["credential"], "identity", 2, 1, 1, allowed_zones=[], blast_radius=1)
    add_action(
        b,
        "omega-cloud-core",
        "host-omega",
        "cloud_sg_block",
        ["exfil"],
        "cloud",
        2,
        2,
        2,
        requires_all_action_types=["dns_sinkhole"],
        blast_radius=2,
    )

    owners = ["edr", "netops", "identity", "soc-lead", "dns", "cloud"]
    families = ["malware", "c2", "credential", "exfil", "lateral", "persistence"]
    for idx in range(30):
        owner = owners[idx % len(owners)]
        family = families[idx % len(families)]
        add_action(
            b,
            f"omega-decoy-{idx:02d}",
            "host-omega",
            f"decoy_type_{idx:02d}",
            [family],
            owner,
            9,
            6,
            5,
            family_confidence={family: 40},
            blast_radius=6,
        )
    return b


def expected_large_branching():
    selected = ["omega-cloud-core", "omega-dns-core", "omega-edr-core", "omega-id-core"]
    owners = ["cloud", "dns", "edr", "identity"]
    summary = {
        "selected_actions": selected,
        "risk_score": 20,
        "review_minutes": 7,
        "outage_units": 5,
        "rule_slots": 5,
        "selected_owners": owners,
    }
    return {
        "status": "accepted",
        "winner": "host-omega",
        **summary,
        "assets": [
            {
                "asset_id": "host-omega",
                "status": "accepted",
                **summary,
                "reasons": [],
            }
        ],
    }


def variant_combinatorial_dependency_mesh():
    b = base_bundle("risk_then_cost")
    b["policy"]["required_families"] = ["malware", "c2", "credential", "exfil", "lateral", "persistence"]
    b["policy"]["threshold"] = 20
    b["policy"]["review_budget"] = 10
    b["policy"]["outage_budget"] = 7
    b["policy"]["rule_slot_budget"] = 8
    b["policy"]["min_distinct_owners"] = 5
    b["policy"]["max_actions_per_owner"] = 2
    b["policy"]["owner_review_caps"] = {"edr": 5, "netops": 4, "cloud": 5, "soc-lead": 4}
    b["policy"]["zone_blast_radius_budget"]["prod"] = 8
    b["policy"]["escalation_outage_threshold"] = 6
    add_asset(b, "host-sigma", criticality=10, detected_at="2026-05-17T12:58:00Z")

    # The canonical solution relies on confidence aggregation across five action types.
    # A greedy single-action family cover misses the credential and malware thresholds.
    core = [
        ("sigma-edr-core", "edr_kill", ["malware", "persistence"], "edr", 2, 1, 1, {"malware": 60, "persistence": 50}, [], []),
        ("sigma-hostfw-core", "host_firewall", ["malware", "credential"], "cloud", 2, 1, 1, {"malware": 40, "credential": 50}, [], ["edr_kill"]),
        ("sigma-id-core", "disable_user", ["credential"], "identity", 2, 1, 1, {"credential": 45}, [["sigma-hostfw-core", "sigma-hostfw-alt-03"]], []),
        ("sigma-dns-core", "dns_sinkhole", ["c2", "lateral"], "dns", 1, 1, 1, {"c2": 80, "lateral": 50}, [], []),
        ("sigma-egress-core", "egress_filter", ["exfil", "c2"], "netops", 2, 2, 2, {"exfil": 70, "c2": 20}, [], ["dns_sinkhole"]),
    ]
    for action_id, action_type, families, owner, review, outage, slots, confidence, requires_any, requires_types in core:
        add_action(
            b,
            action_id,
            "host-sigma",
            action_type,
            families,
            owner,
            review,
            outage,
            slots,
            family_confidence=confidence,
            requires_any=requires_any,
            requires_all_action_types=requires_types,
            blast_radius=1,
        )

    # Alternatives stay inside coarse budgets and mostly pass local gates, but fail only
    # after dependency, confidence, owner-cap, conflict, or final tie comparisons.
    alt_specs = [
        ("edr_kill", "edr", ["malware", "persistence"], {"malware": 55, "persistence": 45}),
        ("host_firewall", "cloud", ["malware", "credential"], {"malware": 35, "credential": 45}),
        ("disable_user", "identity", ["credential"], {"credential": 40}),
        ("dns_sinkhole", "dns", ["c2", "lateral"], {"c2": 75, "lateral": 45}),
        ("egress_filter", "netops", ["exfil", "c2"], {"exfil": 65, "c2": 15}),
        ("memory_scrub", "edr", ["persistence"], {"persistence": 55}),
        ("cloud_sg_block", "cloud", ["exfil"], {"exfil": 75}),
        ("proxy_block", "netops", ["c2"], {"c2": 85}),
        ("ticket_hold", "soc-lead", [], {}),
        ("forensic_snapshot", "soc-lead", ["malware"], {"malware": 30}),
        ("browser_token_revoke", "identity", ["credential"], {"credential": 35}),
        ("route_null", "netops", ["exfil", "lateral"], {"exfil": 60, "lateral": 50}),
    ]
    for type_idx, (action_type, owner, families, confidence) in enumerate(alt_specs):
        for alt_idx in range(6):
            action_id = f"sigma-{action_type}-alt-{alt_idx:02d}"
            requires_any = []
            requires_types = []
            conflicts = []
            review = 1 + (alt_idx % 3)
            outage = 1 + (alt_idx % 2)
            slots = 1 + ((type_idx + alt_idx) % 2)
            if action_type == "host_firewall":
                requires_types = ["edr_kill"]
            if action_type == "egress_filter":
                requires_types = ["dns_sinkhole"]
            if action_type == "disable_user":
                requires_any = [["sigma-hostfw-core", "sigma-host_firewall-alt-03"]]
            if alt_idx == 2:
                conflicts = ["sigma-dns-core"]
            if alt_idx == 4:
                confidence = {family: max(1, amount - 25) for family, amount in confidence.items()}
            if alt_idx == 5:
                review += 3
            add_action(
                b,
                action_id,
                "host-sigma",
                action_type,
                families,
                owner,
                review,
                outage,
                slots,
                family_confidence=confidence,
                requires_any=requires_any,
                requires_all_action_types=requires_types,
                conflicts_with=conflicts,
                blast_radius=1,
            )

    # A tempting broad action has the right families but is impossible because of an
    # empty requires_any group. This catches solvers that ignore impossible OR-groups.
    add_action(
        b,
        "sigma-broad-impossible",
        "host-sigma",
        "isolate_vlan",
        ["malware", "c2", "credential", "exfil", "lateral", "persistence"],
        "netops",
        3,
        4,
        2,
        family_confidence={family: 100 for family in b["policy"]["required_families"]},
        requires_any=[[]],
        blast_radius=2,
    )
    return b


def expected_combinatorial_dependency_mesh():
    selected = [
        "sigma-disable_user-alt-00",
        "sigma-dns-core",
        "sigma-edr-core",
        "sigma-egress-core",
        "sigma-hostfw-core",
    ]
    summary = {
        "selected_actions": selected,
        "risk_score": 20,
        "review_minutes": 8,
        "outage_units": 6,
        "rule_slots": 6,
        "selected_owners": ["cloud", "dns", "edr", "identity", "netops"],
    }
    return {
        "status": "accepted",
        "winner": "host-sigma",
        **summary,
        "assets": [
            {
                "asset_id": "host-sigma",
                "status": "accepted",
                **summary,
                "reasons": [],
            }
        ],
    }


def variant_confidence_side_channel_and_empty_acceptance():
    b = base_bundle("risk_then_cost")
    b["policy"]["required_families"] = ["malware", "c2", "credential", "exfil"]
    b["policy"]["threshold"] = 16
    b["policy"]["review_budget"] = 8
    b["policy"]["outage_budget"] = 5
    b["policy"]["rule_slot_budget"] = 6
    b["policy"]["min_distinct_owners"] = 4
    add_asset(b, "host-sidechannel", criticality=8, detected_at="2026-05-17T12:45:00Z")
    add_asset(b, "host-empty-ok", criticality=1, detected_at="2026-05-17T12:50:00Z")

    add_action(
        b,
        "side-edr-partial",
        "host-sidechannel",
        "edr_kill",
        ["malware"],
        "edr",
        2,
        1,
        1,
        family_confidence={"malware": 60},
    )
    add_action(
        b,
        "side-dns-partial",
        "host-sidechannel",
        "dns_sinkhole",
        ["c2"],
        "dns",
        1,
        1,
        1,
        family_confidence={"c2": 60},
    )
    add_action(
        b,
        "side-id-partial",
        "host-sidechannel",
        "disable_user",
        ["credential"],
        "identity",
        2,
        1,
        1,
        allowed_zones=[],
        family_confidence={"credential": 60},
    )
    add_action(
        b,
        "side-cloud-exfil",
        "host-sidechannel",
        "cloud_sg_block",
        ["exfil"],
        "cloud",
        2,
        1,
        1,
        family_confidence={"exfil": 70},
        requires_all_action_types=["dns_sinkhole"],
    )
    add_action(
        b,
        "side-confidence-only",
        "host-sidechannel",
        "evidence_correlation",
        [],
        "soc-lead",
        1,
        0,
        1,
        family_confidence={"malware": 30, "c2": 20, "credential": 30},
        allowed_zones=[],
    )
    add_action(
        b,
        "side-shortcut-impossible",
        "host-sidechannel",
        "isolate_vlan",
        ["malware", "c2", "credential", "exfil"],
        "netops",
        3,
        4,
        2,
        family_confidence={"malware": 100, "c2": 100, "credential": 100, "exfil": 100},
        requires_any=[["missing-side-action"]],
    )
    return b


def variant_zero_threshold_empty_plan():
    b = base_bundle("cost_then_risk")
    b["policy"]["required_families"] = []
    b["policy"]["threshold"] = 0
    b["policy"]["min_distinct_owners"] = 0
    b["policy"]["review_budget"] = 0
    b["policy"]["outage_budget"] = 0
    b["policy"]["rule_slot_budget"] = 0
    add_asset(b, "host-empty-canonical", criticality=3)
    add_action(b, "expensive-unused", "host-empty-canonical", "edr_kill", ["malware"], "edr", 1, 1, 1)
    return b


def variant_dominance_search_wall():
    b = base_bundle("risk_then_cost")
    b["policy"]["required_families"] = ["malware", "c2", "credential", "exfil", "lateral", "persistence"]
    b["policy"]["threshold"] = 20
    b["policy"]["review_budget"] = 10
    b["policy"]["outage_budget"] = 6
    b["policy"]["rule_slot_budget"] = 8
    b["policy"]["min_distinct_owners"] = 5
    b["policy"]["max_actions_per_owner"] = 2
    b["policy"]["owner_review_caps"] = {"edr": 4, "netops": 4, "cloud": 4, "soc-lead": 4}
    b["policy"]["zone_blast_radius_budget"]["prod"] = 8
    b["policy"]["escalation_outage_threshold"] = 6
    add_asset(b, "host-wall", criticality=10, detected_at="2026-05-17T12:59:00Z")

    core = [
        ("wall-00-edr", "edr_kill", ["malware"], "edr", 2, 1, 1, {"malware": 90}),
        ("wall-01-dns", "dns_sinkhole", ["c2"], "dns", 1, 1, 1, {"c2": 80}),
        ("wall-02-id", "disable_user", ["credential"], "identity", 2, 1, 1, {"credential": 90}),
        ("wall-03-cloud", "cloud_sg_block", ["exfil"], "cloud", 2, 1, 1, {"exfil": 70}),
        ("wall-04-net", "egress_filter", ["lateral"], "netops", 1, 1, 1, {"lateral": 50}),
        ("wall-05-soc", "forensic_snapshot", ["persistence"], "soc-lead", 2, 1, 1, {"persistence": 50}),
    ]
    for action_id, action_type, families, owner, review, outage, slots, confidence in core:
        add_action(
            b,
            action_id,
            "host-wall",
            action_type,
            families,
            owner,
            review,
            outage,
            slots,
            family_confidence=confidence,
            blast_radius=1,
            allowed_zones=[] if action_type == "disable_user" else ["prod"],
        )

    owners = ["edr", "netops", "identity", "soc-lead", "dns", "cloud"]
    families = ["malware", "c2", "credential", "exfil", "lateral", "persistence"]
    for idx in range(60):
        family = families[idx % len(families)]
        owner = owners[(idx * 5 + 1) % len(owners)]
        confidence = 100
        review = 2 + (idx % 3)
        outage = 1 + (idx % 2)
        slots = 1 + ((idx // 3) % 2)
        conflicts = []
        requires_any = []
        requires_types = []
        if idx % 8 == 0:
            confidence = max(1, b["policy"]["family_min_confidence"][family] - 1)
        if idx % 10 == 0:
            conflicts = ["wall-01-dns"]
        if idx % 11 == 0:
            requires_any = [[f"wall-decoy-{idx - 1:02d}" if idx else "missing-wall"]]
        if family == "exfil" and idx % 4 == 1:
            requires_types = ["dns_sinkhole"]
        add_action(
            b,
            f"wall-decoy-{idx:02d}",
            "host-wall",
            f"wall_decoy_type_{idx:02d}",
            [family],
            owner,
            review,
            outage,
            slots,
            family_confidence={family: confidence},
            conflicts_with=conflicts,
            requires_any=requires_any,
            requires_all_action_types=requires_types,
            blast_radius=1,
        )
    return b


def expected_dominance_search_wall():
    selected = ["wall-00-edr", "wall-01-dns", "wall-02-id", "wall-03-cloud", "wall-04-net", "wall-05-soc"]
    summary = {
        "selected_actions": selected,
        "risk_score": 20,
        "review_minutes": 10,
        "outage_units": 6,
        "rule_slots": 6,
        "selected_owners": ["cloud", "dns", "edr", "identity", "netops", "soc-lead"],
    }
    return {
        "status": "accepted",
        "winner": "host-wall",
        **summary,
        "assets": [
            {
                "asset_id": "host-wall",
                "status": "accepted",
                **summary,
                "reasons": [],
            }
        ],
    }


def generated_variants():
    variants = [
        public_bundle(),
        variant_balanced_vs_broad(),
        variant_balanced_vs_broad("cost_then_risk"),
        variant_conflict_and_one_type(),
        variant_asset_tiebreak(),
        variant_no_winner(),
        variant_confidence_dependencies(),
        variant_owner_and_blast_caps(),
        variant_confidence_side_channel_and_empty_acceptance(),
        variant_zero_threshold_empty_plan(),
    ]
    for idx in range(6):
        b = variant_balanced_vs_broad("cost_then_risk" if idx % 2 else "risk_then_cost")
        b["assets"][0]["asset_id"] = f"host-gen-{idx}"
        for action in b["actions"]:
            action["asset_id"] = f"host-gen-{idx}"
            action["action_id"] = f"{action['action_id']}-{idx}"
        if idx == 1:
            b["policy"]["review_budget"] = 6
        if idx == 2:
            b["actions"][0]["expires_at"] = "2026-05-17T12:59:59Z"
        if idx == 3:
            b["actions"][2]["owner"] = "unknown"
        if idx == 4:
            b["assets"][0]["tags"] = ["decommissioned:pending"]
        if idx == 5:
            b["policy"]["threshold"] = 14
            add_action(b, "cloud-extra-5", "host-gen-5", "cloud_sg_block", ["exfil", "c2"], "cloud", 3, 2, 2)
        variants.append(b)
    return variants


def test_public_bundle_integrity():
    assert PUBLIC_BUNDLE.exists()
    assert hashlib.sha256(PUBLIC_BUNDLE.read_bytes()).hexdigest() == PUBLIC_SHA256


def test_public_fixture_exact_output(tmp_path):
    actual = run_cli(public_bundle(), tmp_path)
    assert_exact_schema(actual)
    assert actual == expected(public_bundle())


def test_generated_compatible_variants(tmp_path):
    for idx, bundle in enumerate(generated_variants()):
        actual = run_cli(bundle, tmp_path / f"case-{idx}")
        assert_exact_schema(actual)
        assert actual == expected(bundle), f"variant {idx} mismatch"


def test_large_branching_requires_pruned_search(tmp_path):
    actual = run_cli(variant_large_branching(), tmp_path / "large-branching")
    assert_exact_schema(actual)
    assert actual == expected_large_branching()


def test_combinatorial_dependency_mesh_requires_dynamic_pruning(tmp_path):
    actual = run_cli(variant_combinatorial_dependency_mesh(), tmp_path / "dependency-mesh")
    assert_exact_schema(actual)
    assert actual == expected_combinatorial_dependency_mesh()


def test_confidence_only_contributions_and_empty_plan_semantics(tmp_path):
    bundle = variant_confidence_side_channel_and_empty_acceptance()
    actual = run_cli(bundle, tmp_path / "confidence-side-channel")
    assert_exact_schema(actual)
    assert actual == expected(bundle)


def test_dominance_search_wall_requires_real_pruning(tmp_path):
    actual = run_cli(variant_dominance_search_wall(), tmp_path / "dominance-wall")
    assert_exact_schema(actual)
    assert actual == expected_dominance_search_wall()


def test_requested_path_is_used_and_rerunnable(tmp_path):
    bundle = variant_conflict_and_one_type()
    first = run_cli(bundle, tmp_path / "first")
    second = run_cli(bundle, tmp_path / "second")
    assert first == second == expected(bundle)
    assert (APP / "quarantine-plan").exists()
    assert os.access(APP / "quarantine-plan", os.X_OK)
