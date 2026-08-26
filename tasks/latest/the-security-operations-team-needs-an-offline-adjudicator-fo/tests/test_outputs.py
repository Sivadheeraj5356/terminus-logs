import copy
import hashlib
import hmac
import json
import os
import subprocess
from pathlib import Path

import pytest


WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
CLI = WORKSPACE / "bin" / "breakglass-ledger"
SOURCE_DIR = WORKSPACE / "cmd" / "breakglass-ledger"
SOURCE_FILE = SOURCE_DIR / "main.go"
PUBLIC_INPUT = WORKSPACE / "task_file" / "breakglass_ledger_case.json"
PUBLIC_SHA256 = "55e21040e6a9405608112a0fba904226af5c72f7df2c2b1be08bc0de71c47727"
_BUILT = False

EVENT_REASON_ORDER = [
    "principal_unavailable",
    "principal_inactive",
    "principal_revoked",
    "bad_signature",
    "session_missing",
    "session_closed",
    "session_expired",
    "challenge_mismatch",
    "duplicate_open",
    "role_not_required",
    "clearance_too_low",
    "control_not_required",
    "gateway_mismatch",
    "gateway_locked",
    "route_too_long",
]

DECISION_REASON_ORDER = [
    "event_ignored",
    "token_replayed",
    "route_incomplete",
    "missing_quorum",
    "org_diversity",
    "site_diversity",
    "separation_violation",
    "missing_control",
    "risk_too_high",
]


def read_json(path):
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_sorted(values):
    return sorted(set(values))


def canonical_risk(values):
    return ",".join(unique_sorted(values))


def transcript(event):
    fields = [
        event["id"],
        str(event["revision"]),
        event["type"],
        event["session"],
        event["principal"],
        event["resource"],
        event["role"],
        event["control"],
        event["gateway"],
        event["from_zone"],
        event["to_zone"],
        event["token"],
        event["challenge"],
        str(event["time"]),
        str(event["expires_at"]),
        canonical_risk(event["risk_signals"]),
    ]
    return "\n".join(fields).encode("utf-8")


def sign_event(case, event):
    principals = {row["id"]: row for row in case["principals"]}
    secret = principals[event["principal"]]["secret"].encode("utf-8")
    return hmac.new(secret, transcript(event), hashlib.sha256).hexdigest()


def attach_signatures(case, bad_ids=()):
    bad = set(bad_ids)
    for event in case["events"]:
        if event["id"] in bad:
            event["signature"] = "00" * 32
        else:
            event["signature"] = sign_event(case, event)
    return case


def find_event(case, event_id):
    for event in case["events"]:
        if event["id"] == event_id:
            return event
    raise AssertionError(f"missing event {event_id}")


def find_principal(case, principal_id):
    for principal in case["principals"]:
        if principal["id"] == principal_id:
            return principal
    raise AssertionError(f"missing principal {principal_id}")


def find_resource(case, resource_id):
    for resource in case["resources"]:
        if resource["id"] == resource_id:
            return resource
    raise AssertionError(f"missing resource {resource_id}")


def find_gateway(case, gateway_id):
    for gateway in case["gateways"]:
        if gateway["id"] == gateway_id:
            return gateway
    raise AssertionError(f"missing gateway {gateway_id}")


def event(
    event_id,
    event_type,
    *,
    session="",
    principal="ann",
    resource="",
    role="",
    control="",
    gateway="",
    from_zone="",
    to_zone="",
    token="",
    challenge="",
    revision=1,
    time=0,
    ingest_seq=1,
    expires_at=0,
    risks=None,
):
    return {
        "id": event_id,
        "revision": revision,
        "time": time,
        "ingest_seq": ingest_seq,
        "type": event_type,
        "session": session,
        "principal": principal,
        "resource": resource,
        "role": role,
        "control": control,
        "gateway": gateway,
        "from_zone": from_zone,
        "to_zone": to_zone,
        "token": token,
        "challenge": challenge,
        "expires_at": expires_at,
        "risk_signals": [] if risks is None else list(risks),
        "signature": "",
    }


def public_base():
    return read_json(PUBLIC_INPUT)


def retained_events(events):
    kept = {}
    for row in events:
        current = kept.get(row["id"])
        if current is None:
            kept[row["id"]] = row
            continue
        candidate_key = (
            row["revision"],
            row["time"],
            row["ingest_seq"],
            tuple([-ord(c) for c in row["session"]]),
        )
        current_key = (
            current["revision"],
            current["time"],
            current["ingest_seq"],
            tuple([-ord(c) for c in current["session"]]),
        )
        if candidate_key > current_key:
            kept[row["id"]] = row
    return sorted(kept.values(), key=lambda row: (row["time"], row["ingest_seq"], row["id"]))


def principal_valid_at(principal, at):
    return (
        principal["available"]
        and principal["active_from"] <= at <= principal["active_until"]
        and (principal["revoked_after"] == 0 or at < principal["revoked_after"])
    )


def clearance_ok(case, actual, minimum):
    order = {value: pos for pos, value in enumerate(case["policy"]["clearance_order"])}
    if actual not in order or minimum not in order:
        return False
    return order[actual] <= order[minimum]


def uses_session(event_type):
    return event_type in {"approve", "control", "hop", "activate", "close"}


def ordered_reasons(reasons, order):
    return [reason for reason in order if reason in reasons]


def event_reasons(case, state, row):
    principals = state["principals"]
    resources = state["resources"]
    gateways = state["gateways"]
    gateway_locked = state["gateway_locked"]
    sessions = state["sessions"]
    principal = principals[row["principal"]]
    reasons = set()

    if not principal["available"]:
        reasons.add("principal_unavailable")
    if row["time"] < principal["active_from"] or row["time"] > principal["active_until"]:
        reasons.add("principal_inactive")
    if principal["revoked_after"] != 0 and row["time"] >= principal["revoked_after"]:
        reasons.add("principal_revoked")
    if row["signature"] != sign_event(case, row):
        reasons.add("bad_signature")

    session = sessions.get(row["session"])
    if uses_session(row["type"]):
        if session is None:
            reasons.add("session_missing")
        else:
            if session["state"] == "closed":
                reasons.add("session_closed")
            if row["time"] > session["expires_at"]:
                reasons.add("session_expired")
            if row["challenge"] != session["challenge"]:
                reasons.add("challenge_mismatch")

    if row["type"] == "open":
        existing = sessions.get(row["session"])
        if existing is not None and existing["state"] != "closed":
            reasons.add("duplicate_open")
    elif row["type"] == "approve" and session is not None:
        resource = resources[session["resource"]]
        if row["role"] not in resource["required_roles"]:
            reasons.add("role_not_required")
        if not clearance_ok(case, principal["clearance"], resource["min_clearance"]):
            reasons.add("clearance_too_low")
    elif row["type"] == "control" and session is not None:
        resource = resources[session["resource"]]
        if row["control"] not in resource["required_controls"]:
            reasons.add("control_not_required")
    elif row["type"] == "hop":
        gateway = gateways.get(row["gateway"])
        if gateway is None or gateway["from_zone"] != row["from_zone"] or gateway["to_zone"] != row["to_zone"]:
            reasons.add("gateway_mismatch")
        if session is not None and row["from_zone"] != session["current_zone"]:
            reasons.add("gateway_mismatch")
        if gateway is not None and gateway_locked[row["gateway"]]:
            reasons.add("gateway_locked")
        if session is not None and session["hop_count"] + 1 > case["policy"]["max_route_hops"]:
            reasons.add("route_too_long")
    elif row["type"] in {"lock", "unlock"}:
        gateway = gateways.get(row["gateway"])
        if gateway is None or gateway["from_zone"] != row["from_zone"] or gateway["to_zone"] != row["to_zone"]:
            reasons.add("gateway_mismatch")

    return ordered_reasons(reasons, EVENT_REASON_ORDER)


def apply_event(state, row):
    sessions = state["sessions"]
    principals = state["principals"]
    gateway_locked = state["gateway_locked"]
    if row["type"] == "open":
        principal = principals[row["principal"]]
        sessions[row["session"]] = {
            "session": row["session"],
            "resource": row["resource"],
            "challenge": row["challenge"],
            "expires_at": row["expires_at"],
            "open_time": row["time"],
            "state": "open",
            "current_zone": principal["site"],
            "hop_count": 0,
            "activation_count": 0,
            "consumed": False,
            "route": [principal["site"]],
            "approvals": [],
            "controls": [],
        }
    elif row["type"] == "approve" and row["session"] in sessions:
        sessions[row["session"]]["approvals"].append(
            {
                "event_id": row["id"],
                "role": row["role"],
                "principal": row["principal"],
                "time": row["time"],
            }
        )
    elif row["type"] == "control" and row["session"] in sessions:
        sessions[row["session"]]["controls"].append(
            {
                "event_id": row["id"],
                "control": row["control"],
                "principal": row["principal"],
                "time": row["time"],
            }
        )
    elif row["type"] == "hop" and row["session"] in sessions:
        session = sessions[row["session"]]
        session["route"].append(row["to_zone"])
        session["current_zone"] = row["to_zone"]
        session["hop_count"] += 1
    elif row["type"] == "lock" and row["gateway"] in gateway_locked:
        gateway_locked[row["gateway"]] = True
    elif row["type"] == "unlock" and row["gateway"] in gateway_locked:
        gateway_locked[row["gateway"]] = False
    elif row["type"] == "close" and row["session"] in sessions:
        sessions[row["session"]]["state"] = "closed"


def approval_rows(resource, usable):
    providers = {role: [] for role in resource["required_roles"]}
    for approval in usable:
        if approval["role"] in providers:
            providers[approval["role"]].append(f"{approval['event_id']}:{approval['principal']}")
    return [
        {"role": role, "providers": unique_sorted(providers[role])}
        for role in resource["required_roles"]
    ], providers


def control_rows(resource, usable):
    providers = {control: [] for control in resource["required_controls"]}
    for control in usable:
        if control["control"] in providers:
            providers[control["control"]].append(f"{control['event_id']}:{control['principal']}")
    return [
        {"control": control, "providers": unique_sorted(providers[control])}
        for control in resource["required_controls"]
    ], providers


def separation_violation(resource, principals, usable):
    role_principals = {role: set() for role in resource["required_roles"]}
    role_orgs = {role: set() for role in resource["required_roles"]}
    for approval in usable:
        if approval["role"] not in role_principals:
            continue
        principal = principals[approval["principal"]]
        role_principals[approval["role"]].add(approval["principal"])
        role_orgs[approval["role"]].add(principal["org"])

    for left, right in resource["separation_pairs"]:
        if role_principals[left] & role_principals[right]:
            return True
    for left, right in resource["org_separation_pairs"]:
        if role_orgs[left] & role_orgs[right]:
            return True
    return False


def risk_score(case, resource, session, row, usable_approvals):
    principals = {principal["id"]: principal for principal in case["principals"]}
    risk = resource["base_risk"]
    for signal in set(row["risk_signals"]):
        risk += case["policy"]["risk_signal_scores"].get(signal, 0)
    external = {
        approval["principal"]
        for approval in usable_approvals
        if principals[approval["principal"]]["external"]
    }
    risk += 6 * len(external)
    if 2 * (row["time"] - session["open_time"]) > (session["expires_at"] - session["open_time"]):
        risk += 4
    if session["hop_count"] == case["policy"]["max_route_hops"]:
        risk += 3
    return risk


def build_decision(case, state, row, finding):
    sessions = state["sessions"]
    principals = state["principals"]
    resources = state["resources"]
    reasons = set()
    if finding["status"] == "ignored":
        reasons.add("event_ignored")

    session = sessions.get(row["session"])
    if session is None:
        return {
            "id": row["id"],
            "session": row["session"],
            "resource": row["resource"],
            "status": "deny",
            "risk_score": 0,
            "reasons": ordered_reasons(reasons, DECISION_REASON_ORDER),
            "approvals": [],
            "controls": [],
            "route": [],
        }

    resource = resources[session["resource"]]
    usable_approvals = []
    for approval in session["approvals"]:
        principal = principals[approval["principal"]]
        if (
            row["time"] - approval["time"] <= case["policy"]["approval_window"]
            and principal_valid_at(principal, row["time"])
        ):
            usable_approvals.append(approval)
    usable_controls = [
        control
        for control in session["controls"]
        if row["time"] - control["time"] <= case["policy"]["control_window"]
    ]

    approvals, approval_providers = approval_rows(resource, usable_approvals)
    controls, control_providers = control_rows(resource, usable_controls)

    if session["consumed"]:
        reasons.add("token_replayed")
    if session["current_zone"] != resource["zone"]:
        reasons.add("route_incomplete")
    if any(not approval_providers[role] for role in resource["required_roles"]):
        reasons.add("missing_quorum")

    orgs = {principals[approval["principal"]]["org"] for approval in usable_approvals}
    sites = {principals[approval["principal"]]["site"] for approval in usable_approvals}
    if len(orgs) < resource["min_distinct_orgs"]:
        reasons.add("org_diversity")
    if len(sites) < resource["min_distinct_sites"]:
        reasons.add("site_diversity")
    if separation_violation(resource, principals, usable_approvals):
        reasons.add("separation_violation")
    if any(not control_providers[control] for control in resource["required_controls"]):
        reasons.add("missing_control")

    risk = risk_score(case, resource, session, row, usable_approvals)
    if risk > case["policy"]["deny_above"]:
        reasons.add("risk_too_high")

    ordered = ordered_reasons(reasons, DECISION_REASON_ORDER)
    if ordered:
        status = "deny"
    elif risk > case["policy"]["step_up_after"]:
        status = "step_up"
    else:
        status = "allow"

    return {
        "id": row["id"],
        "session": row["session"],
        "resource": session["resource"],
        "status": status,
        "risk_score": risk,
        "reasons": ordered,
        "approvals": approvals,
        "controls": controls,
        "route": list(session["route"]),
    }


def oracle(case):
    state = {
        "principals": {row["id"]: row for row in case["principals"]},
        "resources": {row["id"]: row for row in case["resources"]},
        "gateways": {row["id"]: row for row in case["gateways"]},
        "gateway_locked": {row["id"]: row["initially_locked"] for row in case["gateways"]},
        "sessions": {},
    }
    output = {
        "event_findings": [],
        "decisions": [],
        "final_sessions": [],
        "consumed_sessions": [],
    }
    for row in retained_events(case["events"]):
        reasons = event_reasons(case, state, row)
        finding = {
            "id": row["id"],
            "type": row["type"],
            "status": "accepted" if not reasons else "ignored",
            "reasons": reasons,
        }
        output["event_findings"].append(finding)
        if row["type"] == "activate":
            decision = build_decision(case, state, row, finding)
            output["decisions"].append(decision)
            if finding["status"] == "accepted" and decision["status"] in {"allow", "step_up"}:
                session = state["sessions"][row["session"]]
                session["consumed"] = True
                session["activation_count"] += 1
                session["state"] = "activated"
        if not reasons:
            apply_event(state, row)

    for session_id in sorted(state["sessions"]):
        session = state["sessions"][session_id]
        output["final_sessions"].append(
            {
                "session": session_id,
                "resource": session["resource"],
                "state": session["state"],
                "current_zone": session["current_zone"],
                "hop_count": session["hop_count"],
                "activation_count": session["activation_count"],
            }
        )
        if session["consumed"]:
            output["consumed_sessions"].append(session_id)
    output["consumed_sessions"].sort()
    return output


def assert_contract_shape(actual):
    assert set(actual) == {"event_findings", "decisions", "final_sessions", "consumed_sessions"}
    assert isinstance(actual["event_findings"], list)
    assert isinstance(actual["decisions"], list)
    assert isinstance(actual["final_sessions"], list)
    assert isinstance(actual["consumed_sessions"], list)
    assert actual["consumed_sessions"] == sorted(actual["consumed_sessions"])

    for row in actual["event_findings"]:
        assert set(row) == {"id", "type", "status", "reasons"}
        assert row["status"] in {"accepted", "ignored"}
        assert row["reasons"] == [reason for reason in EVENT_REASON_ORDER if reason in row["reasons"]]
        assert len(row["reasons"]) == len(set(row["reasons"]))

    for row in actual["decisions"]:
        assert set(row) == {
            "id",
            "session",
            "resource",
            "status",
            "risk_score",
            "reasons",
            "approvals",
            "controls",
            "route",
        }
        assert row["status"] in {"allow", "step_up", "deny"}
        assert isinstance(row["risk_score"], int)
        assert row["reasons"] == [reason for reason in DECISION_REASON_ORDER if reason in row["reasons"]]
        for approval in row["approvals"]:
            assert set(approval) == {"role", "providers"}
            assert approval["providers"] == sorted(approval["providers"])
        for control in row["controls"]:
            assert set(control) == {"control", "providers"}
            assert control["providers"] == sorted(control["providers"])
        assert isinstance(row["route"], list)

    assert [row["session"] for row in actual["final_sessions"]] == sorted(
        row["session"] for row in actual["final_sessions"]
    )
    for row in actual["final_sessions"]:
        assert set(row) == {
            "session",
            "resource",
            "state",
            "current_zone",
            "hop_count",
            "activation_count",
        }
        assert row["state"] in {"open", "activated", "closed"}
        assert isinstance(row["hop_count"], int)
        assert isinstance(row["activation_count"], int)


def build_cli():
    global _BUILT
    if _BUILT:
        return
    assert SOURCE_FILE.exists(), f"missing Go source at {SOURCE_FILE}"
    source_text = SOURCE_FILE.read_text(encoding="utf-8")
    lowered = source_text.lower()
    forbidden = [
        "os/exec",
        "exec.command",
        "syscall.exec",
        "python",
        "pip install",
        "curl ",
        "wget ",
        "go get",
        "/bin/bash",
        "/bin/sh",
    ]
    for needle in forbidden:
        assert needle not in lowered, f"forbidden helper-process pattern found: {needle}"
    CLI.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GO111MODULE"] = "off"
    subprocess.run(
        ["go", "build", "-o", str(CLI), "."],
        cwd=SOURCE_DIR,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    assert CLI.exists(), f"expected built binary at {CLI}"
    _BUILT = True


def run_case(case_name, case_data, tmp_path):
    build_cli()
    input_path = tmp_path / f"{case_name}.json"
    output_path = tmp_path / f"{case_name}.out.json"
    write_json(input_path, case_data)
    output_path.write_text('{"stale": true}\n', encoding="utf-8")
    subprocess.run(
        [str(CLI), str(input_path), str(output_path)],
        cwd=WORKSPACE,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    actual = read_json(output_path)
    expected = oracle(copy.deepcopy(case_data))
    assert_contract_shape(actual)
    assert actual == expected

    output_path.write_text('{"stale": "again"}\n', encoding="utf-8")
    subprocess.run(
        [str(CLI), str(input_path), str(output_path)],
        cwd=WORKSPACE,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    assert read_json(output_path) == expected


def hidden_cases():
    cases = []

    case = copy.deepcopy(public_base())
    find_event(case, "e-008-control-packet")["signature"] = "11" * 32
    cases.append(("bad_signature_control_is_ignored_and_control_missing", case))

    case = copy.deepcopy(public_base())
    find_gateway(case, "g-b-vault")["initially_locked"] = True
    cases.append(("initially_locked_gateway_blocks_route_and_activation", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].insert(
        8,
        event(
            "e-008b-unlock-b-vault",
            "unlock",
            principal="mira",
            gateway="g-b-vault",
            from_zone="zone-b",
            to_zone="vault",
            time=148,
            ingest_seq=85,
        ),
    )
    find_gateway(case, "g-b-vault")["initially_locked"] = True
    cases.append(("unlock_event_restores_locked_gateway_before_hop", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-010-activate-kms")["time"] = 230
    find_event(case, "e-010-activate-kms")["revision"] = 3
    cases.append(("approval_window_expiry_removes_old_quorum", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-010-activate-kms")["time"] = 216
    find_event(case, "e-010-activate-kms")["revision"] = 3
    cases.append(("control_window_strict_boundary_keeps_controls", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-010-activate-kms")["time"] = 217
    find_event(case, "e-010-activate-kms")["revision"] = 3
    cases.append(("control_window_one_past_boundary_drops_first_control", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_principal(case, "cyd")["revoked_after"] = 160
    cases.append(("revocation_after_approval_invalidates_activation_quorum", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-006-approve-network")["principal"] = "ann"
    cases.append(("principal_role_separation_denies_even_with_quorum", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-006-approve-network")["principal"] = "mira"
    find_principal(case, "mira")["active_from"] = 0
    find_principal(case, "mira")["active_until"] = 500
    cases.append(("org_separation_denies_sec_org_on_custodian_and_network", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-009b-extra-hop",
            "hop",
            session="s-kms",
            principal="ann",
            resource="kms-root",
            gateway="g-c-vault",
            from_zone="vault",
            to_zone="vault",
            token="tok-kms",
            challenge="chal-kms",
            time=160,
            ingest_seq=95,
        )
    )
    case["gateways"].append({"id": "g-loop-vault", "from_zone": "vault", "to_zone": "vault", "initially_locked": False})
    find_event(case, "e-009b-extra-hop")["gateway"] = "g-loop-vault"
    find_event(case, "e-009b-extra-hop")["from_zone"] = "vault"
    find_event(case, "e-009b-extra-hop")["to_zone"] = "vault"
    case["events"].append(
        event(
            "e-009c-too-far",
            "hop",
            session="s-kms",
            principal="ann",
            resource="kms-root",
            gateway="g-loop-vault",
            from_zone="vault",
            to_zone="vault",
            token="tok-kms",
            challenge="chal-kms",
            time=161,
            ingest_seq=96,
        )
    )
    case["policy"]["max_route_hops"] = 3
    cases.append(("route_too_long_ignores_only_the_overflow_hop", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"] = [row for row in case["events"] if row["id"] != "e-009-hop-b-vault"]
    cases.append(("route_incomplete_when_final_hop_missing", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-030-missing-activate",
            "activate",
            session="s-ghost",
            principal="ann",
            resource="kms-root",
            token="tok-ghost",
            challenge="ghost",
            time=300,
            ingest_seq=30,
        )
    )
    cases.append(("activation_for_missing_session_has_empty_state_arrays", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    duplicate = copy.deepcopy(find_event(case, "e-010-activate-kms"))
    duplicate["revision"] = 2
    duplicate["time"] = 172
    duplicate["ingest_seq"] = 11
    duplicate["session"] = "a-session-wins-final-tie"
    case["events"].append(duplicate)
    cases.append(("duplicate_retention_final_tie_uses_lexicographic_session", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-025-activate-bastion")["risk_signals"] = ["malware_hint", "suspicious_ip"]
    cases.append(("risk_too_high_denies_with_otherwise_valid_state", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["policy"]["step_up_after"] = 20
    find_event(case, "e-025-activate-bastion")["risk_signals"] = ["after_hours"]
    cases.append(("strict_step_up_threshold_without_denial", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    find_event(case, "e-025-activate-bastion")["challenge"] = "wrong"
    cases.append(("ignored_activation_still_reports_available_state_reasons", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-031-inactive-principal-unlock",
            "unlock",
            principal="mira",
            gateway="g-a-b",
            from_zone="zone-a",
            to_zone="zone-b",
            time=99,
            ingest_seq=31,
        )
    )
    cases.append(("principal_inactive_is_reported_before_state_replay", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-032-expired-session-control",
            "control",
            session="s-bastion",
            principal="ann",
            resource="bastion-core",
            control="witness",
            token="tok-bastion",
            challenge="chal-bastion",
            time=320,
            ingest_seq=32,
        )
    )
    cases.append(("session_expired_is_reported_after_session_deadline", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-033-duplicate-open",
            "open",
            session="s-kms",
            principal="ann",
            resource="kms-root",
            token="tok-kms-duplicate",
            challenge="chal-kms-duplicate",
            time=105,
            ingest_seq=33,
            expires_at=280,
        )
    )
    cases.append(("duplicate_open_has_no_state_effect", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-034-unrequired-role",
            "approve",
            session="s-kms",
            principal="ben",
            resource="kms-root",
            role="observer",
            token="tok-kms",
            challenge="chal-kms",
            time=132,
            ingest_seq=34,
        )
    )
    cases.append(("role_not_required_is_ignored_without_poisoning_quorum", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["principals"].append(
        {
            "id": "nora",
            "org": "audit",
            "site": "zone-e",
            "clearance": "standard",
            "secret": "nora-ledger-key",
            "available": True,
            "active_from": 0,
            "active_until": 500,
            "revoked_after": 0,
            "external": False,
        }
    )
    case["events"].append(
        event(
            "e-035-low-clearance-approval",
            "approve",
            session="s-kms",
            principal="nora",
            resource="kms-root",
            role="custodian",
            token="tok-kms",
            challenge="chal-kms",
            time=133,
            ingest_seq=35,
        )
    )
    cases.append(("clearance_too_low_prevents_approval_use", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-036-unrequired-control",
            "control",
            session="s-kms",
            principal="ben",
            resource="kms-root",
            control="screen_recording",
            token="tok-kms",
            challenge="chal-kms",
            time=146,
            ingest_seq=36,
        )
    )
    cases.append(("control_not_required_is_reported_and_ignored", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"].append(
        event(
            "e-037-hop-gateway-mismatch",
            "hop",
            session="s-kms",
            principal="ann",
            resource="kms-root",
            gateway="g-b-vault",
            from_zone="zone-a",
            to_zone="vault",
            token="tok-kms",
            challenge="chal-kms",
            time=149,
            ingest_seq=37,
        )
    )
    cases.append(("gateway_mismatch_hop_is_ignored_before_valid_route", attach_signatures(case)))

    case = copy.deepcopy(public_base())
    case["events"] = list(reversed(case["events"]))
    case["principals"] = list(reversed(case["principals"]))
    case["resources"] = list(reversed(case["resources"]))
    case["gateways"] = list(reversed(case["gateways"]))
    cases.append(("input_order_invariance_except_replay_sort", attach_signatures(case)))

    return cases


def test_cli_rejects_missing_positional_arguments():
    build_cli()
    without_args = subprocess.run(
        [str(CLI)],
        cwd=WORKSPACE,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert without_args.returncode != 0
    with_one_arg = subprocess.run(
        [str(CLI), str(PUBLIC_INPUT)],
        cwd=WORKSPACE,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert with_one_arg.returncode != 0


def test_output_parent_directory_is_created(tmp_path):
    build_cli()
    case_data = public_base()
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "nested" / "reports" / "breakglass_ledger_report.json"
    write_json(input_path, case_data)
    assert not output_path.parent.exists()
    subprocess.run(
        [str(CLI), str(input_path), str(output_path)],
        cwd=WORKSPACE,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    assert read_json(output_path) == oracle(copy.deepcopy(case_data))


def test_public_fixture_integrity_and_output(tmp_path):
    assert PUBLIC_INPUT.exists(), f"missing public fixture {PUBLIC_INPUT}"
    assert sha256(PUBLIC_INPUT) == PUBLIC_SHA256
    run_case("public", public_base(), tmp_path)


def test_generated_cases_cover_all_documented_reason_codes():
    event_reasons = set()
    decision_reasons = set()
    for _case_name, case_data in [("public", public_base()), *hidden_cases()]:
        expected = oracle(copy.deepcopy(case_data))
        for finding in expected["event_findings"]:
            event_reasons.update(finding["reasons"])
        for decision in expected["decisions"]:
            decision_reasons.update(decision["reasons"])

    assert event_reasons == set(EVENT_REASON_ORDER)
    assert decision_reasons == set(DECISION_REASON_ORDER)


@pytest.mark.parametrize("case_name,case_data", hidden_cases())
def test_hidden_compatible_variants(case_name, case_data, tmp_path):
    run_case(case_name, case_data, tmp_path)
