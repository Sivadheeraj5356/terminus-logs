import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path


APP = Path("/app")


def read_tsv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def split_list(value):
    if value in ("", "-"):
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def sha256_hex(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def zone_allowed(zones, zone):
    return "*" in zones or zone in zones


def ticket_ok(ticket):
    return (
        len(ticket) == 10
        and ticket[:4] in {"INC-", "CHG-"}
        and ticket[4:].isdigit()
    )


def ip_to_int(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    out = 0
    for part in parts:
        try:
            octet = int(part)
        except ValueError:
            return None
        if not 0 <= octet <= 255:
            return None
        out = (out << 8) | octet
    return out


def cidr_contains(cidr, ip):
    if "/" not in cidr:
        return False
    network, prefix = cidr.split("/", 1)
    network_int = ip_to_int(network)
    ip_int = ip_to_int(ip)
    if network_int is None or ip_int is None:
        return False
    try:
        prefix_int = int(prefix)
    except ValueError:
        return False
    if not 0 <= prefix_int <= 32:
        return False
    mask = 0 if prefix_int == 0 else (0xFFFFFFFF << (32 - prefix_int)) & 0xFFFFFFFF
    return (network_int & mask) == (ip_int & mask)


def ip_allowed(cidrs, ip):
    return not cidrs or any(cidr_contains(cidr, ip) for cidr in cidrs)


def minutes(start, end):
    from datetime import datetime

    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return int((datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds() // 60)


def add(entry_list, control, severity, principal, resource, evidence, reasons):
    evidence = sorted(set(evidence))
    reasons = sorted(set(reasons))
    entry_list.append(
        {
            "entry_id": "",
            "control": control,
            "severity": severity,
            "principal": principal,
            "resource": resource,
            "first_evidence": evidence[0],
            "evidence": evidence,
            "reason_codes": reasons,
        }
    )


def expected_review(base):
    """Independent implementation of the public SPEC.md rules."""
    principals = {r["principal"]: r for r in read_tsv(base / "principals.tsv")}
    resources = {r["resource"]: r for r in read_tsv(base / "resources.tsv")}
    tickets = {r["ticket"]: r for r in read_tsv(base / "tickets.tsv")}
    approvers = {r["approver"]: r for r in read_tsv(base / "approvers.tsv")}
    requests = read_tsv(base / "requests.tsv")
    request_by_id = {r["request_id"]: r for r in requests}
    approvals = read_tsv(base / "approvals.tsv")
    events = read_tsv(base / "events.tsv")
    revocations = read_tsv(base / "revocations.tsv")

    approvals_by_request = {}
    for approval in approvals:
        approvals_by_request.setdefault(approval["request_id"], []).append(approval)

    ledger_entries = []
    authorized = {}
    valid_critical_approvals = []

    for request in requests:
        # Request-level checks: requester eligibility, duration/ticket policy,
        # approval validity, and final authorization status.
        principal = principals.get(request["requester"])
        resource = resources.get(request["resource"])
        eligibility = []
        if principal is None:
            eligibility.append("missing_requester")
        else:
            if principal["status"] != "active":
                eligibility.append("inactive_requester")
            if principal["mfa"] != "true":
                eligibility.append("mfa_missing")
            if resource is not None:
                if not zone_allowed(split_list(principal["zones"]), resource["zone"]):
                    eligibility.append("zone_not_allowed")
                if principal["role"] in split_list(resource["forbidden_roles"]):
                    eligibility.append("forbidden_role")
        if eligibility:
            add(ledger_entries, "requester-not-eligible", "critical", request["requester"], request["resource"], [f"request:{request['request_id']}"], eligibility)

        duration_ticket = []
        if resource is not None:
            if minutes(request["start_ts"], request["end_ts"]) > int(resource["max_minutes"]):
                duration_ticket.append("duration_exceeds_max")
            if resource["tier"] == "critical" and not ticket_ok(request["ticket"]):
                duration_ticket.append("critical_ticket_invalid")
        if duration_ticket:
            severity = "high" if "duration_exceeds_max" in duration_ticket else "medium"
            add(ledger_entries, "duration-or-ticket-violation", severity, request["requester"], request["resource"], [f"request:{request['request_id']}"], duration_ticket)

        if resource is not None and not ip_allowed(split_list(resource["allowed_cidrs"]), request["source_ip"]):
            add(ledger_entries, "network-boundary-violation", "high", request["requester"], request["resource"], [f"request:{request['request_id']}"], ["request_source_out_of_range"])

        if request["ticket"] != "-":
            ticket = tickets.get(request["ticket"])
            ticket_reasons = []
            ticket_evidence = [f"request:{request['request_id']}"]
            if ticket is None:
                ticket_reasons.append("ticket_missing")
            else:
                ticket_evidence.append(f"ticket:{request['ticket']}")
                if ticket["requester"] != request["requester"]:
                    ticket_reasons.append("ticket_requester_mismatch")
                if ticket["resource"] != request["resource"]:
                    ticket_reasons.append("ticket_resource_mismatch")
                if ticket["opened_ts"] > request["start_ts"] or (ticket["closed_ts"] != "-" and ticket["closed_ts"] < request["end_ts"]):
                    ticket_reasons.append("ticket_not_open_for_window")
                if resource is not None and resource["tier"] == "critical" and ticket["emergency"] != "true":
                    ticket_reasons.append("ticket_not_emergency_for_critical")
                if not ip_allowed(split_list(ticket["allowed_cidrs"]), request["source_ip"]):
                    add(ledger_entries, "ticket-scope-violation", "high", request["requester"], request["resource"], [f"request:{request['request_id']}", f"ticket:{request['ticket']}"], ["request_source_outside_ticket_cidr"])
            if ticket_reasons:
                add(ledger_entries, "ticket-binding-violation", "high", request["requester"], request["resource"], ticket_evidence, ticket_reasons)

        approval_reasons = []
        approval_evidence = [f"request:{request['request_id']}"]
        valid_approvers = set()
        valid_teams = set()
        if resource is not None:
            for approval in approvals_by_request.get(request["request_id"], []):
                if approval["decision"] != "approve":
                    continue
                row_reasons = []
                approver = approvers.get(approval["approver"])
                expected = None
                if approver is not None:
                    expected = sha256_hex("|".join([approver["secret"], approval["approval_id"], approval["request_id"], approval["approver"], approval["decision"], approval["ts"]]))
                if expected != approval["signature"]:
                    row_reasons.append("signature_invalid")
                if approver is not None:
                    if approver["status"] != "active":
                        row_reasons.append("approver_inactive")
                    if not zone_allowed(split_list(approver["zones"]), resource["zone"]):
                        row_reasons.append("approver_zone_not_allowed")
                    authority_ok = approver["authority"] == "security" or (
                        approver["authority"] == "owner" and approver["team"] == resource["owner_team"]
                    )
                    if not authority_ok:
                        row_reasons.append("approver_authority_invalid")
                if approval["approver"] == request["requester"]:
                    row_reasons.append("self_approval")
                if principal is not None and approval["approver"] in principals:
                    if principal["manager"] == principals[approval["approver"]]["manager"]:
                        row_reasons.append("shared_manager")
                if approval["ts"] > request["start_ts"]:
                    row_reasons.append("late_approval")
                if row_reasons:
                    approval_evidence.append(f"approval:{approval['approval_id']}")
                    approval_reasons.extend(row_reasons)
                else:
                    valid_approvers.add(approval["approver"])
                    valid_teams.add(approver["team"])
                    if resource["tier"] == "critical":
                        valid_critical_approvals.append((approval["approver"], approval["approval_id"], request["request_id"], request["start_ts"]))
            needed = 2 if resource["dual_control"] == "true" else 1
            count_ok = len(valid_approvers) >= needed and (resource["dual_control"] != "true" or len(valid_teams) >= needed)
            if not count_ok:
                approval_reasons.append("insufficient_approvals")
            if approval_reasons:
                add(ledger_entries, "approval-control-failure", "critical", request["requester"], request["resource"], approval_evidence, approval_reasons)
            authorized[request["request_id"]] = not eligibility and not duration_ticket and count_ok
        else:
            authorized[request["request_id"]] = False

    previous_hash = "GENESIS"
    for index, event in enumerate(events):
        # Physical event order is part of the hash-chain rule.
        reasons = []
        expected = sha256_hex("|".join([event["prev_hash"], event["event_id"], event["request_id"], event["ts"], event["actor"], event["session_id"], event["source_ip"], event["command"]]))
        if expected != event["event_hash"]:
            reasons.append("event_hash_invalid")
        if index == 0 and event["prev_hash"] != "GENESIS":
            reasons.append("first_prev_not_genesis")
        if index > 0 and event["prev_hash"] != previous_hash:
            reasons.append("prev_hash_mismatch")
        if reasons:
            request = request_by_id.get(event["request_id"], {})
            add(ledger_entries, "ledger-integrity-break", "critical", event["actor"], request.get("resource", "unknown"), [f"event:{event['event_id']}"], reasons)
        previous_hash = event["event_hash"]

    for event in events:
        # Event-level security checks depend on the already computed request
        # authorization state.
        request = request_by_id.get(event["request_id"])
        if request is None or request["resource"] not in resources:
            continue
        resource = resources[request["resource"]]
        if event["ts"] < request["start_ts"] or event["ts"] > request["end_ts"]:
            add(ledger_entries, "access-outside-window", "high", event["actor"], request["resource"], [f"event:{event['event_id']}"], ["event_outside_request_window"])
        matching_revocations = [
            r for r in revocations
            if r["principal"] == event["actor"] and r["resource"] == request["resource"] and r["effective_ts"] <= event["ts"]
        ]
        if matching_revocations:
            revocation = sorted(matching_revocations, key=lambda r: r["effective_ts"])[0]
            add(
                ledger_entries,
                "post-revocation-access",
                "critical",
                event["actor"],
                request["resource"],
                [f"event:{event['event_id']}", f"revocation:{revocation['principal']}:{revocation['resource']}:{revocation['effective_ts']}"],
                ["revocation_effective"],
            )
        if event["command"] in split_list(resource["privileged_commands"]):
            reasons = []
            if not authorized.get(event["request_id"], False):
                reasons.append("request_not_authorized")
            if event["actor"] != request["requester"]:
                reasons.append("actor_mismatch")
            if reasons:
                add(ledger_entries, "unapproved-command", "high", event["actor"], request["resource"], [f"event:{event['event_id']}"], reasons)
        if event["source_ip"] != request["source_ip"]:
            add(ledger_entries, "source-ip-drift", "medium", event["actor"], request["resource"], [f"event:{event['event_id']}"], ["source_ip_changed"])
        if not ip_allowed(split_list(resource["allowed_cidrs"]), event["source_ip"]):
            add(ledger_entries, "network-boundary-violation", "high", event["actor"], request["resource"], [f"event:{event['event_id']}"], ["event_source_out_of_range"])
        ticket = tickets.get(request["ticket"])
        if ticket is not None:
            reasons = []
            if not ip_allowed(split_list(ticket["allowed_cidrs"]), event["source_ip"]):
                reasons.append("event_source_outside_ticket_cidr")
            if split_list(ticket["allowed_commands"]) and event["command"] not in split_list(ticket["allowed_commands"]):
                reasons.append("event_command_outside_ticket_scope")
            if reasons:
                add(ledger_entries, "ticket-scope-violation", "high", event["actor"], request["resource"], [f"event:{event['event_id']}", f"ticket:{request['ticket']}"], reasons)

    authorized_by_principal = {}
    for request in requests:
        if authorized.get(request["request_id"], False):
            authorized_by_principal.setdefault(request["requester"], []).append(request)
    for principal_name, reqs in authorized_by_principal.items():
        # Concurrent-session ledger_entries aggregate all overlapping authorized
        # request windows per requester.
        max_active = int(principals[principal_name]["max_active"])
        evidence = set()
        for request in reqs:
            overlap = [other for other in reqs if request["start_ts"] <= other["end_ts"] and other["start_ts"] <= request["end_ts"]]
            if len(overlap) > max_active:
                evidence.update(f"request:{other['request_id']}" for other in overlap)
        if evidence:
            add(ledger_entries, "concurrent-session-limit", "medium", principal_name, "multiple", sorted(evidence), ["max_active_exceeded"])

    events_by_session = {}
    for event in events:
        if event["session_id"] and event["session_id"] != "-":
            events_by_session.setdefault(event["session_id"], []).append(event)
    for session_events in events_by_session.values():
        actors = {event["actor"] for event in session_events}
        ips = {event["source_ip"] for event in session_events}
        reasons = []
        if len(actors) > 1:
            reasons.append("session_actor_changed")
        if len(ips) > 1:
            reasons.append("session_source_ip_changed")
        if reasons:
            add(ledger_entries, "session-handoff-detected", "high", "multiple", "multiple", [f"event:{event['event_id']}" for event in session_events], reasons)

    approvals_by_approver = {}
    for approver, approval_id, request_id, start_ts in valid_critical_approvals:
        approvals_by_approver.setdefault(approver, []).append((approval_id, request_id, start_ts))
    for approver, approval_rows in approvals_by_approver.items():
        approval_rows = sorted(approval_rows, key=lambda row: (row[2], row[0]))
        evidence = set()
        for _, _, start_ts in approval_rows:
            from datetime import datetime

            fmt = "%Y-%m-%dT%H:%M:%SZ"
            start = datetime.strptime(start_ts, fmt)
            window = []
            request_ids = set()
            for approval_id, request_id, candidate_ts in approval_rows:
                delta = (datetime.strptime(candidate_ts, fmt) - start).total_seconds()
                if 0 <= delta <= 180 * 60:
                    window.append(approval_id)
                    request_ids.add(request_id)
            if len(request_ids) > 2:
                evidence.update(f"approval:{approval_id}" for approval_id in window)
        if evidence:
            add(ledger_entries, "approval-concentration-risk", "medium", approver, "multiple", sorted(evidence), ["critical_approval_burst"])

    ledger_entries.sort(key=lambda f: (f["first_evidence"], f["control"], f["principal"], f["resource"]))
    for index, entry in enumerate(ledger_entries, start=1):
        entry["entry_id"] = f"BRK-{index:04d}"
    severity_index = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for entry in ledger_entries:
        severity_index[entry["severity"]] += 1
    return {"ledger_entries": ledger_entries, "severity_index": severity_index}


def write_tsv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def signature(secret, approval_id, request_id, approver, decision, ts):
    return sha256_hex("|".join([secret, approval_id, request_id, approver, decision, ts]))


def event_hash(prev_hash, event_id, request_id, ts, actor, session_id, source_ip, command):
    return sha256_hex("|".join([prev_hash, event_id, request_id, ts, actor, session_id, source_ip, command]))


def make_alternate_fixture(base):
    base.mkdir()
    write_tsv(base / "principals.tsv", [
        {"principal": "zoe", "role": "admin", "team": "ops", "status": "active", "mfa": "true", "manager": "m1", "zones": "prod", "max_active": "1"},
        {"principal": "yan", "role": "intern", "team": "ops", "status": "active", "mfa": "true", "manager": "m2", "zones": "prod", "max_active": "1"},
        {"principal": "mia", "role": "admin", "team": "ops", "status": "inactive", "mfa": "false", "manager": "m3", "zones": "prod", "max_active": "1"},
        {"principal": "kai", "role": "admin", "team": "ops", "status": "active", "mfa": "true", "manager": "m4", "zones": "stage", "max_active": "1"},
    ], ["principal", "role", "team", "status", "mfa", "manager", "zones", "max_active"])
    write_tsv(base / "resources.tsv", [
        {"resource": "root-host", "zone": "prod", "tier": "critical", "owner_team": "ops", "max_minutes": "30", "dual_control": "false", "forbidden_roles": "intern", "allowed_cidrs": "1.1.1.0/24,3.3.3.0/24,4.4.4.0/24", "privileged_commands": "sudo,sh"},
    ], ["resource", "zone", "tier", "owner_team", "max_minutes", "dual_control", "forbidden_roles", "allowed_cidrs", "privileged_commands"])
    write_tsv(base / "tickets.tsv", [
        {"ticket": "CHG-000001", "requester": "zoe", "resource": "root-host", "opened_ts": "2026-05-31T23:00:00Z", "closed_ts": "2026-06-01T00:30:00Z", "emergency": "true", "allowed_cidrs": "1.1.1.0/28", "allowed_commands": "sudo"},
        {"ticket": "INC-000002", "requester": "yan", "resource": "root-host", "opened_ts": "2026-06-01T00:00:00Z", "closed_ts": "2026-06-01T00:12:00Z", "emergency": "false", "allowed_cidrs": "2.2.2.0/24", "allowed_commands": "sudo"},
        {"ticket": "CHG-000003", "requester": "zoe", "resource": "root-host", "opened_ts": "2026-06-01T00:00:00Z", "closed_ts": "-", "emergency": "true", "allowed_cidrs": "3.3.3.0/24", "allowed_commands": "sh"},
        {"ticket": "CHG-000004", "requester": "zoe", "resource": "root-host", "opened_ts": "2026-06-01T00:00:00Z", "closed_ts": "2026-06-01T00:30:00Z", "emergency": "true", "allowed_cidrs": "1.1.1.0/24", "allowed_commands": "sudo"},
        {"ticket": "BAD", "requester": "mia", "resource": "root-host", "opened_ts": "2026-06-01T00:45:00Z", "closed_ts": "2026-06-01T02:00:00Z", "emergency": "false", "allowed_cidrs": "4.4.4.0/24", "allowed_commands": "sudo"},
    ], ["ticket", "requester", "resource", "opened_ts", "closed_ts", "emergency", "allowed_cidrs", "allowed_commands"])
    write_tsv(base / "approvers.tsv", [
        {"approver": "quinn", "team": "security", "status": "active", "zones": "*", "authority": "security", "secret": "qsecret"},
        {"approver": "olive", "team": "ops", "status": "active", "zones": "prod", "authority": "owner", "secret": "osecret"},
        {"approver": "zoe", "team": "ops", "status": "active", "zones": "prod", "authority": "owner", "secret": "zsecret"},
        {"approver": "nina", "team": "ops", "status": "active", "zones": "stage", "authority": "owner", "secret": "nsecret"},
    ], ["approver", "team", "status", "zones", "authority", "secret"])
    write_tsv(base / "requests.tsv", [
        {"request_id": "R-A", "requester": "zoe", "resource": "root-host", "start_ts": "2026-06-01T00:00:00Z", "end_ts": "2026-06-01T00:20:00Z", "ticket": "CHG-000001", "reason": "kernel patch", "source_ip": "1.1.1.1"},
        {"request_id": "R-B", "requester": "yan", "resource": "root-host", "start_ts": "2026-06-01T00:05:00Z", "end_ts": "2026-06-01T00:15:00Z", "ticket": "INC-000002", "reason": "assist", "source_ip": "2.2.2.2"},
        {"request_id": "R-C", "requester": "kai", "resource": "root-host", "start_ts": "2026-06-01T00:10:00Z", "end_ts": "2026-06-01T00:20:00Z", "ticket": "CHG-000003", "reason": "control-review", "source_ip": "3.3.3.3"},
        {"request_id": "R-D", "requester": "zoe", "resource": "root-host", "start_ts": "2026-06-01T00:10:00Z", "end_ts": "2026-06-01T00:25:00Z", "ticket": "CHG-000004", "reason": "followup", "source_ip": "1.1.1.1"},
        {"request_id": "R-E", "requester": "mia", "resource": "root-host", "start_ts": "2026-06-01T00:30:00Z", "end_ts": "2026-06-01T01:20:00Z", "ticket": "BAD", "reason": "late repair", "source_ip": "4.4.4.4"},
    ], ["request_id", "requester", "resource", "start_ts", "end_ts", "ticket", "reason", "source_ip"])
    approvals = [
        {"approval_id": "A-A", "request_id": "R-A", "approver": "quinn", "decision": "approve", "ts": "2026-05-31T23:50:00Z", "secret": "qsecret"},
        {"approval_id": "A-B", "request_id": "R-B", "approver": "olive", "decision": "approve", "ts": "2026-06-01T00:00:00Z", "secret": "osecret"},
        {"approval_id": "A-C", "request_id": "R-C", "approver": "nina", "decision": "approve", "ts": "2026-06-01T00:00:00Z", "secret": "nsecret"},
        {"approval_id": "A-D", "request_id": "R-D", "approver": "quinn", "decision": "approve", "ts": "2026-06-01T00:01:00Z", "secret": "qsecret"},
        {"approval_id": "A-D2", "request_id": "R-D", "approver": "zoe", "decision": "approve", "ts": "2026-06-01T00:02:00Z", "secret": "zsecret"},
        {"approval_id": "A-E", "request_id": "R-E", "approver": "quinn", "decision": "approve", "ts": "2026-06-01T00:20:00Z", "secret": "qsecret"},
    ]
    write_tsv(base / "approvals.tsv", [
        {k: row[k] for k in ["approval_id", "request_id", "approver", "decision", "ts"]} | {
            "signature": signature(row["secret"], row["approval_id"], row["request_id"], row["approver"], row["decision"], row["ts"])
        }
        for row in approvals
    ], ["approval_id", "request_id", "approver", "decision", "ts", "signature"])
    events = [
        ["E-A", "R-A", "2026-06-01T00:01:00Z", "zoe", "s1", "1.1.1.1", "sudo"],
        ["E-B", "R-B", "2026-06-01T00:06:00Z", "yan", "s2", "2.2.2.3", "sh"],
        ["E-C", "R-C", "2026-06-01T00:12:00Z", "kai", "s3", "3.3.3.3", "sudo"],
        ["E-D", "R-D", "2026-06-01T00:26:00Z", "zoe", "s4", "1.1.1.1", "sudo"],
        ["E-E", "R-E", "2026-06-01T00:35:00Z", "mia", "s5", "4.4.4.4", "sudo"],
        ["E-F", "R-A", "2026-06-01T00:02:00Z", "yan", "s1", "1.1.1.20", "sh"],
    ]
    rows = []
    prev = "GENESIS"
    for event in events:
        h = event_hash(prev, *event)
        rows.append({"event_id": event[0], "request_id": event[1], "ts": event[2], "actor": event[3], "session_id": event[4], "source_ip": event[5], "command": event[6], "prev_hash": prev, "event_hash": h})
        prev = h
    rows[-1]["prev_hash"] = "bad-prev"
    rows[-1]["event_hash"] = "f" * 64
    write_tsv(base / "events.tsv", rows, ["event_id", "request_id", "ts", "actor", "session_id", "source_ip", "command", "prev_hash", "event_hash"])
    write_tsv(base / "revocations.tsv", [
        {"principal": "zoe", "resource": "root-host", "effective_ts": "2026-06-01T00:24:00Z", "reason": "suspected token theft"}
    ], ["principal", "resource", "effective_ts", "reason"])


def run_program(env=None):
    output_path = Path(env.get("BREAKGLASS_OUT", APP / "output_data" / "breakglass_ledger.json")) if env else APP / "output_data" / "breakglass_ledger.json"
    if output_path.exists():
        output_path.unlink()
    full_env = os.environ.copy()
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    subprocess.run(["cargo", "run", "--quiet"], cwd=APP, env=full_env, check=True, timeout=60)
    assert output_path.exists(), f"missing output file at {output_path}"
    with open(output_path, encoding="utf-8") as handle:
        return json.load(handle)


def assert_review_shape(review):
    assert set(review) == {"ledger_entries", "severity_index"}
    assert set(review["severity_index"]) == {"critical", "high", "medium", "low"}
    ids = [entry["entry_id"] for entry in review["ledger_entries"]]
    assert ids == [f"BRK-{i:04d}" for i in range(1, len(ids) + 1)]
    sort_keys = [(f["first_evidence"], f["control"], f["principal"], f["resource"]) for f in review["ledger_entries"]]
    assert sort_keys == sorted(sort_keys)
    for entry in review["ledger_entries"]:
        assert set(entry) == {"entry_id", "control", "severity", "principal", "resource", "first_evidence", "evidence", "reason_codes"}
        assert entry["evidence"] == sorted(set(entry["evidence"]))
        assert entry["reason_codes"] == sorted(set(entry["reason_codes"]))
        assert entry["first_evidence"] == entry["evidence"][0]


def test_bundled_breakglass_ledger_exact_ledger():
    """The bundled ledger exercises every major entry family."""
    review = run_program()
    expected = expected_review(APP / "input_data")
    assert_review_shape(review)
    assert review == expected
    assert review["severity_index"] == {"critical": 8, "high": 13, "medium": 6, "low": 0}


def test_alternate_fixture_uses_path_overrides_and_full_rules(tmp_path):
    """A generated fixture prevents hardcoding and verifies env path overrides."""
    fixture = tmp_path / "fixture"
    make_alternate_fixture(fixture)
    out = tmp_path / "out" / "ledger_entries.json"
    env = {
        "BREAKGLASS_PRINCIPALS": fixture / "principals.tsv",
        "BREAKGLASS_RESOURCES": fixture / "resources.tsv",
        "BREAKGLASS_TICKETS": fixture / "tickets.tsv",
        "BREAKGLASS_APPROVERS": fixture / "approvers.tsv",
        "BREAKGLASS_REQUESTS": fixture / "requests.tsv",
        "BREAKGLASS_APPROVALS": fixture / "approvals.tsv",
        "BREAKGLASS_EVENTS": fixture / "events.tsv",
        "BREAKGLASS_REVOCATIONS": fixture / "revocations.tsv",
        "BREAKGLASS_OUT": out,
    }
    review = run_program(env)
    expected = expected_review(fixture)
    assert_review_shape(review)
    assert review == expected
    controls = {entry["control"] for entry in review["ledger_entries"]}
    assert {
        "requester-not-eligible",
        "approval-control-failure",
        "approval-concentration-risk",
        "duration-or-ticket-violation",
        "ledger-integrity-break",
        "access-outside-window",
        "network-boundary-violation",
        "session-handoff-detected",
        "post-revocation-access",
        "ticket-binding-violation",
        "ticket-scope-violation",
        "unapproved-command",
        "source-ip-drift",
        "concurrent-session-limit",
    }.issubset(controls)
