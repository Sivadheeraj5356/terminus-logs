#!/usr/bin/env bash
set -euo pipefail

cat > /app/src/main.rs <<'RS'
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::env;
use std::fs;
use std::io::Write;
use std::process::{Command, Stdio};

type Row = HashMap<String, String>;

#[derive(Clone, Default)]
struct Principal {
    role: String,
    status: String,
    mfa: String,
    manager: String,
    zones: Vec<String>,
    max_active: usize,
}

#[derive(Clone, Default)]
struct Resource {
    zone: String,
    tier: String,
    owner_team: String,
    max_minutes: i64,
    dual_control: bool,
    forbidden_roles: Vec<String>,
    allowed_cidrs: Vec<String>,
    privileged_commands: Vec<String>,
}

#[derive(Clone, Default)]
struct Ticket {
    requester: String,
    resource: String,
    opened_ts: String,
    closed_ts: String,
    emergency: bool,
    allowed_cidrs: Vec<String>,
    allowed_commands: Vec<String>,
}

#[derive(Clone, Default)]
struct Approver {
    team: String,
    status: String,
    zones: Vec<String>,
    authority: String,
    secret: String,
}

#[derive(Clone, Default)]
struct Request {
    request_id: String,
    requester: String,
    resource: String,
    start_ts: String,
    end_ts: String,
    ticket: String,
    source_ip: String,
}

#[derive(Clone, Default)]
struct Approval {
    approval_id: String,
    request_id: String,
    approver: String,
    decision: String,
    ts: String,
    signature: String,
}

#[derive(Clone, Default)]
struct Event {
    event_id: String,
    request_id: String,
    ts: String,
    actor: String,
    session_id: String,
    source_ip: String,
    command: String,
    prev_hash: String,
    event_hash: String,
}

#[derive(Clone, Default)]
struct Revocation {
    principal: String,
    resource: String,
    effective_ts: String,
}

#[derive(Clone)]
struct LedgerEntry {
    entry_id: String,
    control: String,
    severity: String,
    principal: String,
    resource: String,
    evidence: Vec<String>,
    reasons: Vec<String>,
}

fn path(var: &str, default_path: &str) -> String {
    env::var(var).unwrap_or_else(|_| default_path.to_string())
}

fn list(raw: &str) -> Vec<String> {
    if raw.trim().is_empty() || raw.trim() == "-" {
        Vec::new()
    } else {
        raw.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()
    }
}

fn read_tsv(path: &str) -> Vec<Row> {
    let text = fs::read_to_string(path).unwrap_or_else(|e| panic!("failed to read {path}: {e}"));
    let mut lines = text.lines().filter(|l| !l.trim().is_empty());
    let headers: Vec<String> = lines.next().unwrap_or("").split('\t').map(|s| s.to_string()).collect();
    lines.map(|line| {
        let vals: Vec<&str> = line.split('\t').collect();
        headers.iter().enumerate().map(|(i, h)| {
            (h.clone(), vals.get(i).copied().unwrap_or("").to_string())
        }).collect()
    }).collect()
}

fn sha256_hex(input: &str) -> String {
    let mut child = Command::new("sha256sum")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("sha256sum unavailable");
    child.stdin.as_mut().unwrap().write_all(input.as_bytes()).unwrap();
    let output = child.wait_with_output().unwrap();
    String::from_utf8(output.stdout).unwrap().split_whitespace().next().unwrap().to_string()
}

fn zone_allowed(zones: &[String], zone: &str) -> bool {
    zones.iter().any(|z| z == "*" || z == zone)
}

fn has(xs: &[String], x: &str) -> bool {
    xs.iter().any(|v| v == x)
}

fn parse_ts(ts: &str) -> i64 {
    let y: i64 = ts[0..4].parse().unwrap();
    let m: i64 = ts[5..7].parse().unwrap();
    let d: i64 = ts[8..10].parse().unwrap();
    let hh: i64 = ts[11..13].parse().unwrap();
    let mm: i64 = ts[14..16].parse().unwrap();
    let ss: i64 = ts[17..19].parse().unwrap();
    let days = days_from_civil(y, m, d);
    days * 86_400 + hh * 3_600 + mm * 60 + ss
}

fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = y - if m <= 2 { 1 } else { 0 };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = m + if m > 2 { -3 } else { 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

fn duration_minutes(req: &Request) -> i64 {
    (parse_ts(&req.end_ts) - parse_ts(&req.start_ts)) / 60
}

fn ticket_ok(ticket: &str) -> bool {
    let b = ticket.as_bytes();
    if b.len() != 10 { return false; }
    let prefix = &ticket[0..4];
    (prefix == "INC-" || prefix == "CHG-") && b[4..].iter().all(|c| c.is_ascii_digit())
}

fn ip_to_u32(ip: &str) -> Option<u32> {
    let parts: Vec<&str> = ip.split('.').collect();
    if parts.len() != 4 { return None; }
    let mut out = 0u32;
    for part in parts {
        let octet: u8 = part.parse().ok()?;
        out = (out << 8) | octet as u32;
    }
    Some(out)
}

fn cidr_contains(cidr: &str, ip: &str) -> bool {
    let (network, prefix_raw) = match cidr.split_once('/') {
        Some(value) => value,
        None => return false,
    };
    let network_ip = match ip_to_u32(network) {
        Some(value) => value,
        None => return false,
    };
    let candidate_ip = match ip_to_u32(ip) {
        Some(value) => value,
        None => return false,
    };
    let prefix = match prefix_raw.parse::<u32>() {
        Ok(value) => value,
        Err(_) => return false,
    };
    if prefix > 32 { return false; }
    let mask = if prefix == 0 { 0 } else { u32::MAX << (32 - prefix) };
    (network_ip & mask) == (candidate_ip & mask)
}

fn ip_allowed(cidrs: &[String], ip: &str) -> bool {
    cidrs.is_empty() || cidrs.iter().any(|cidr| cidr_contains(cidr, ip))
}

fn add(ledger_entries: &mut Vec<LedgerEntry>, control: &str, severity: &str, principal: &str, resource: &str, evidence: Vec<String>, reasons: Vec<String>) {
    let mut evidence: Vec<String> = evidence.into_iter().collect::<BTreeSet<_>>().into_iter().collect();
    let reasons: Vec<String> = reasons.into_iter().collect::<BTreeSet<_>>().into_iter().collect();
    if evidence.is_empty() {
        evidence.push("unknown".to_string());
    }
    ledger_entries.push(LedgerEntry {
        entry_id: String::new(),
        control: control.to_string(),
        severity: severity.to_string(),
        principal: principal.to_string(),
        resource: resource.to_string(),
        evidence,
        reasons,
    });
}

fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn json_arr(xs: &[String]) -> String {
    xs.iter().map(|x| format!("\"{}\"", esc(x))).collect::<Vec<_>>().join(",")
}

fn main() {
    let principals_path = path("BREAKGLASS_PRINCIPALS", "/app/input_data/principals.tsv");
    let resources_path = path("BREAKGLASS_RESOURCES", "/app/input_data/resources.tsv");
    let tickets_path = path("BREAKGLASS_TICKETS", "/app/input_data/tickets.tsv");
    let approvers_path = path("BREAKGLASS_APPROVERS", "/app/input_data/approvers.tsv");
    let requests_path = path("BREAKGLASS_REQUESTS", "/app/input_data/requests.tsv");
    let approvals_path = path("BREAKGLASS_APPROVALS", "/app/input_data/approvals.tsv");
    let events_path = path("BREAKGLASS_EVENTS", "/app/input_data/events.tsv");
    let revocations_path = path("BREAKGLASS_REVOCATIONS", "/app/input_data/revocations.tsv");
    let out_path = path("BREAKGLASS_OUT", "/app/output_data/breakglass_ledger.json");

    let principals: HashMap<String, Principal> = read_tsv(&principals_path).into_iter().map(|r| {
        (r["principal"].clone(), Principal {
            role: r["role"].clone(),
            status: r["status"].clone(),
            mfa: r["mfa"].clone(),
            manager: r["manager"].clone(),
            zones: list(&r["zones"]),
            max_active: r["max_active"].parse().unwrap_or(0),
        })
    }).collect();
    let resources: HashMap<String, Resource> = read_tsv(&resources_path).into_iter().map(|r| {
        (r["resource"].clone(), Resource {
            zone: r["zone"].clone(),
            tier: r["tier"].clone(),
            owner_team: r["owner_team"].clone(),
            max_minutes: r["max_minutes"].parse().unwrap_or(0),
            dual_control: r["dual_control"] == "true",
            forbidden_roles: list(&r["forbidden_roles"]),
            allowed_cidrs: list(&r["allowed_cidrs"]),
            privileged_commands: list(&r["privileged_commands"]),
        })
    }).collect();
    let tickets: HashMap<String, Ticket> = read_tsv(&tickets_path).into_iter().map(|r| {
        (r["ticket"].clone(), Ticket {
            requester: r["requester"].clone(),
            resource: r["resource"].clone(),
            opened_ts: r["opened_ts"].clone(),
            closed_ts: r["closed_ts"].clone(),
            emergency: r["emergency"] == "true",
            allowed_cidrs: list(&r["allowed_cidrs"]),
            allowed_commands: list(&r["allowed_commands"]),
        })
    }).collect();
    let approvers: HashMap<String, Approver> = read_tsv(&approvers_path).into_iter().map(|r| {
        (r["approver"].clone(), Approver {
            team: r["team"].clone(),
            status: r["status"].clone(),
            zones: list(&r["zones"]),
            authority: r["authority"].clone(),
            secret: r["secret"].clone(),
        })
    }).collect();
    let requests: Vec<Request> = read_tsv(&requests_path).into_iter().map(|r| Request {
        request_id: r["request_id"].clone(),
        requester: r["requester"].clone(),
        resource: r["resource"].clone(),
        start_ts: r["start_ts"].clone(),
        end_ts: r["end_ts"].clone(),
        ticket: r["ticket"].clone(),
        source_ip: r["source_ip"].clone(),
    }).collect();
    let approvals: Vec<Approval> = read_tsv(&approvals_path).into_iter().map(|r| Approval {
        approval_id: r["approval_id"].clone(),
        request_id: r["request_id"].clone(),
        approver: r["approver"].clone(),
        decision: r["decision"].clone(),
        ts: r["ts"].clone(),
        signature: r["signature"].clone(),
    }).collect();
    let events: Vec<Event> = read_tsv(&events_path).into_iter().map(|r| Event {
        event_id: r["event_id"].clone(),
        request_id: r["request_id"].clone(),
        ts: r["ts"].clone(),
        actor: r["actor"].clone(),
        session_id: r["session_id"].clone(),
        source_ip: r["source_ip"].clone(),
        command: r["command"].clone(),
        prev_hash: r["prev_hash"].clone(),
        event_hash: r["event_hash"].clone(),
    }).collect();
    let revocations: Vec<Revocation> = read_tsv(&revocations_path).into_iter().map(|r| Revocation {
        principal: r["principal"].clone(),
        resource: r["resource"].clone(),
        effective_ts: r["effective_ts"].clone(),
    }).collect();

    let request_by_id: HashMap<String, Request> = requests.iter().map(|r| (r.request_id.clone(), r.clone())).collect();
    let mut approvals_by_request: HashMap<String, Vec<Approval>> = HashMap::new();
    for approval in &approvals {
        approvals_by_request.entry(approval.request_id.clone()).or_default().push(approval.clone());
    }

    let mut ledger_entries = Vec::new();
    let mut authorized: HashMap<String, bool> = HashMap::new();
    let mut valid_critical_approvals: Vec<(String, String, String, String)> = Vec::new();

    for req in &requests {
        let principal = principals.get(&req.requester);
        let resource = resources.get(&req.resource);
        let mut eligibility_reasons = Vec::new();
        if principal.is_none() {
            eligibility_reasons.push("missing_requester".to_string());
        }
        if let Some(p) = principal {
            if p.status != "active" { eligibility_reasons.push("inactive_requester".to_string()); }
            if p.mfa != "true" { eligibility_reasons.push("mfa_missing".to_string()); }
            if let Some(res) = resource {
                if !zone_allowed(&p.zones, &res.zone) { eligibility_reasons.push("zone_not_allowed".to_string()); }
                if has(&res.forbidden_roles, &p.role) { eligibility_reasons.push("forbidden_role".to_string()); }
            }
        }
        if !eligibility_reasons.is_empty() {
            add(&mut ledger_entries, "requester-not-eligible", "critical", &req.requester, &req.resource, vec![format!("request:{}", req.request_id)], eligibility_reasons.clone());
        }

        let mut duration_ticket_reasons = Vec::new();
        if let Some(res) = resource {
            if duration_minutes(req) > res.max_minutes {
                duration_ticket_reasons.push("duration_exceeds_max".to_string());
            }
            if res.tier == "critical" && !ticket_ok(&req.ticket) {
                duration_ticket_reasons.push("critical_ticket_invalid".to_string());
            }
        }
        if !duration_ticket_reasons.is_empty() {
            let severity = if duration_ticket_reasons.iter().any(|r| r == "duration_exceeds_max") { "high" } else { "medium" };
            add(&mut ledger_entries, "duration-or-ticket-violation", severity, &req.requester, &req.resource, vec![format!("request:{}", req.request_id)], duration_ticket_reasons.clone());
        }
        if let Some(res) = resource {
            if !ip_allowed(&res.allowed_cidrs, &req.source_ip) {
                add(&mut ledger_entries, "network-boundary-violation", "high", &req.requester, &req.resource, vec![format!("request:{}", req.request_id)], vec!["request_source_out_of_range".to_string()]);
            }
        }
        if req.ticket != "-" {
            let ticket = tickets.get(&req.ticket);
            let mut ticket_reasons = Vec::new();
            let mut ticket_evidence = vec![format!("request:{}", req.request_id)];
            if let Some(t) = ticket {
                ticket_evidence.push(format!("ticket:{}", req.ticket));
                if t.requester != req.requester { ticket_reasons.push("ticket_requester_mismatch".to_string()); }
                if t.resource != req.resource { ticket_reasons.push("ticket_resource_mismatch".to_string()); }
                if t.opened_ts > req.start_ts || (t.closed_ts != "-" && t.closed_ts < req.end_ts) {
                    ticket_reasons.push("ticket_not_open_for_window".to_string());
                }
                if resource.map(|r| r.tier.as_str()) == Some("critical") && !t.emergency {
                    ticket_reasons.push("ticket_not_emergency_for_critical".to_string());
                }
                if !ip_allowed(&t.allowed_cidrs, &req.source_ip) {
                    add(&mut ledger_entries, "ticket-scope-violation", "high", &req.requester, &req.resource, vec![format!("request:{}", req.request_id), format!("ticket:{}", req.ticket)], vec!["request_source_outside_ticket_cidr".to_string()]);
                }
            } else {
                ticket_reasons.push("ticket_missing".to_string());
            }
            if !ticket_reasons.is_empty() {
                add(&mut ledger_entries, "ticket-binding-violation", "high", &req.requester, &req.resource, ticket_evidence, ticket_reasons);
            }
        }

        let mut approval_reasons = Vec::new();
        let mut approval_evidence = vec![format!("request:{}", req.request_id)];
        let mut valid_approvers = BTreeSet::new();
        let mut valid_teams = BTreeSet::new();
        if let Some(res) = resource {
            for approval in approvals_by_request.get(&req.request_id).cloned().unwrap_or_default() {
                if approval.decision != "approve" {
                    continue;
                }
                let mut row_reasons = Vec::new();
                let app = approvers.get(&approval.approver);
                let expected_sig = app.map(|a| sha256_hex(&format!("{}|{}|{}|{}|{}|{}", a.secret, approval.approval_id, approval.request_id, approval.approver, approval.decision, approval.ts)));
                if expected_sig.as_deref() != Some(approval.signature.as_str()) {
                    row_reasons.push("signature_invalid".to_string());
                }
                if let Some(a) = app {
                    if a.status != "active" { row_reasons.push("approver_inactive".to_string()); }
                    if !zone_allowed(&a.zones, &res.zone) { row_reasons.push("approver_zone_not_allowed".to_string()); }
                    let authority_ok = a.authority == "security" || (a.authority == "owner" && a.team == res.owner_team);
                    if !authority_ok { row_reasons.push("approver_authority_invalid".to_string()); }
                }
                if approval.approver == req.requester {
                    row_reasons.push("self_approval".to_string());
                }
                if let (Some(requester), Some(_)) = (principal, app) {
                    if let Some(approver_principal) = principals.get(&approval.approver) {
                        if requester.manager == approver_principal.manager {
                            row_reasons.push("shared_manager".to_string());
                        }
                    }
                }
                if approval.ts > req.start_ts {
                    row_reasons.push("late_approval".to_string());
                }
                if row_reasons.is_empty() {
                    valid_approvers.insert(approval.approver.clone());
                    if let Some(a) = app {
                        valid_teams.insert(a.team.clone());
                    }
                    if res.tier == "critical" {
                        valid_critical_approvals.push((approval.approver.clone(), approval.approval_id.clone(), req.request_id.clone(), req.start_ts.clone()));
                    }
                } else {
                    approval_evidence.push(format!("approval:{}", approval.approval_id));
                    approval_reasons.extend(row_reasons);
                }
            }
            let needed = if res.dual_control { 2 } else { 1 };
            let count_ok = valid_approvers.len() >= needed && (!res.dual_control || valid_teams.len() >= needed);
            if !count_ok {
                approval_reasons.push("insufficient_approvals".to_string());
            }
            if !approval_reasons.is_empty() {
                add(&mut ledger_entries, "approval-control-failure", "critical", &req.requester, &req.resource, approval_evidence, approval_reasons);
            }
            authorized.insert(req.request_id.clone(), eligibility_reasons.is_empty() && duration_ticket_reasons.is_empty() && count_ok);
        } else {
            authorized.insert(req.request_id.clone(), false);
        }
    }

    let mut previous_hash = "GENESIS".to_string();
    for (idx, event) in events.iter().enumerate() {
        let mut reasons = Vec::new();
        let expected_hash = sha256_hex(&format!("{}|{}|{}|{}|{}|{}|{}|{}", event.prev_hash, event.event_id, event.request_id, event.ts, event.actor, event.session_id, event.source_ip, event.command));
        if expected_hash != event.event_hash {
            reasons.push("event_hash_invalid".to_string());
        }
        if idx == 0 && event.prev_hash != "GENESIS" {
            reasons.push("first_prev_not_genesis".to_string());
        }
        if idx > 0 && event.prev_hash != previous_hash {
            reasons.push("prev_hash_mismatch".to_string());
        }
        if !reasons.is_empty() {
            add(&mut ledger_entries, "ledger-integrity-break", "critical", &event.actor, request_by_id.get(&event.request_id).map(|r| r.resource.as_str()).unwrap_or("unknown"), vec![format!("event:{}", event.event_id)], reasons);
        }
        previous_hash = event.event_hash.clone();
    }

    for event in &events {
        let req = match request_by_id.get(&event.request_id) {
            Some(value) => value,
            None => continue,
        };
        let res = match resources.get(&req.resource) {
            Some(value) => value,
            None => continue,
        };
        if event.ts < req.start_ts || event.ts > req.end_ts {
            add(&mut ledger_entries, "access-outside-window", "high", &event.actor, &req.resource, vec![format!("event:{}", event.event_id)], vec!["event_outside_request_window".to_string()]);
        }
        if let Some(rev) = revocations.iter().filter(|r| r.principal == event.actor && r.resource == req.resource && r.effective_ts <= event.ts).min_by_key(|r| r.effective_ts.clone()) {
            add(&mut ledger_entries, "post-revocation-access", "critical", &event.actor, &req.resource, vec![format!("event:{}", event.event_id), format!("revocation:{}:{}:{}", rev.principal, rev.resource, rev.effective_ts)], vec!["revocation_effective".to_string()]);
        }
        if has(&res.privileged_commands, &event.command) {
            let mut reasons = Vec::new();
            if !authorized.get(&event.request_id).copied().unwrap_or(false) {
                reasons.push("request_not_authorized".to_string());
            }
            if event.actor != req.requester {
                reasons.push("actor_mismatch".to_string());
            }
            if !reasons.is_empty() {
                add(&mut ledger_entries, "unapproved-command", "high", &event.actor, &req.resource, vec![format!("event:{}", event.event_id)], reasons);
            }
        }
        if event.source_ip != req.source_ip {
            add(&mut ledger_entries, "source-ip-drift", "medium", &event.actor, &req.resource, vec![format!("event:{}", event.event_id)], vec!["source_ip_changed".to_string()]);
        }
        if !ip_allowed(&res.allowed_cidrs, &event.source_ip) {
            add(&mut ledger_entries, "network-boundary-violation", "high", &event.actor, &req.resource, vec![format!("event:{}", event.event_id)], vec!["event_source_out_of_range".to_string()]);
        }
        if let Some(ticket) = tickets.get(&req.ticket) {
            let mut reasons = Vec::new();
            if !ip_allowed(&ticket.allowed_cidrs, &event.source_ip) {
                reasons.push("event_source_outside_ticket_cidr".to_string());
            }
            if !ticket.allowed_commands.is_empty() && !has(&ticket.allowed_commands, &event.command) {
                reasons.push("event_command_outside_ticket_scope".to_string());
            }
            if !reasons.is_empty() {
                add(&mut ledger_entries, "ticket-scope-violation", "high", &event.actor, &req.resource, vec![format!("event:{}", event.event_id), format!("ticket:{}", req.ticket)], reasons);
            }
        }
    }

    let mut authorized_by_principal: HashMap<String, Vec<Request>> = HashMap::new();
    for req in &requests {
        if authorized.get(&req.request_id).copied().unwrap_or(false) {
            authorized_by_principal.entry(req.requester.clone()).or_default().push(req.clone());
        }
    }
    for (principal_name, reqs) in authorized_by_principal {
        let max_active = principals.get(&principal_name).map(|p| p.max_active).unwrap_or(0);
        if max_active == 0 { continue; }
        let mut evidence = BTreeSet::new();
        for req in &reqs {
            let concurrent = reqs.iter().filter(|other| req.start_ts <= other.end_ts && other.start_ts <= req.end_ts).count();
            if concurrent > max_active {
                for other in reqs.iter().filter(|other| req.start_ts <= other.end_ts && other.start_ts <= req.end_ts) {
                    evidence.insert(format!("request:{}", other.request_id));
                }
            }
        }
        if !evidence.is_empty() {
            add(&mut ledger_entries, "concurrent-session-limit", "medium", &principal_name, "multiple", evidence.into_iter().collect(), vec!["max_active_exceeded".to_string()]);
        }
    }

    let mut events_by_session: HashMap<String, Vec<Event>> = HashMap::new();
    for event in &events {
        if !event.session_id.is_empty() && event.session_id != "-" {
            events_by_session.entry(event.session_id.clone()).or_default().push(event.clone());
        }
    }
    for (_session_id, session_events) in events_by_session {
        let actors: BTreeSet<String> = session_events.iter().map(|e| e.actor.clone()).collect();
        let ips: BTreeSet<String> = session_events.iter().map(|e| e.source_ip.clone()).collect();
        let mut reasons = Vec::new();
        if actors.len() > 1 { reasons.push("session_actor_changed".to_string()); }
        if ips.len() > 1 { reasons.push("session_source_ip_changed".to_string()); }
        if !reasons.is_empty() {
            let evidence = session_events.iter().map(|e| format!("event:{}", e.event_id)).collect();
            add(&mut ledger_entries, "session-handoff-detected", "high", "multiple", "multiple", evidence, reasons);
        }
    }

    let mut approvals_by_approver: HashMap<String, Vec<(String, String, String)>> = HashMap::new();
    for (approver, approval_id, request_id, start_ts) in valid_critical_approvals {
        approvals_by_approver.entry(approver).or_default().push((approval_id, request_id, start_ts));
    }
    for (approver, mut approvals_for_approver) in approvals_by_approver {
        approvals_for_approver.sort_by(|a, b| a.2.cmp(&b.2).then(a.0.cmp(&b.0)));
        let mut evidence = BTreeSet::new();
        for i in 0..approvals_for_approver.len() {
            let start = parse_ts(&approvals_for_approver[i].2);
            let mut request_ids = BTreeSet::new();
            let mut approval_ids = BTreeSet::new();
            for (approval_id, request_id, ts) in &approvals_for_approver {
                let delta = parse_ts(ts) - start;
                if delta >= 0 && delta <= 180 * 60 {
                    request_ids.insert(request_id.clone());
                    approval_ids.insert(approval_id.clone());
                }
            }
            if request_ids.len() > 2 {
                evidence.extend(approval_ids.into_iter().map(|id| format!("approval:{}", id)));
            }
        }
        if !evidence.is_empty() {
            add(&mut ledger_entries, "approval-concentration-risk", "medium", &approver, "multiple", evidence.into_iter().collect(), vec!["critical_approval_burst".to_string()]);
        }
    }

    ledger_entries.sort_by(|a, b| {
        (a.evidence[0].clone(), a.control.clone(), a.principal.clone(), a.resource.clone())
            .cmp(&(b.evidence[0].clone(), b.control.clone(), b.principal.clone(), b.resource.clone()))
    });
    for (i, entry) in ledger_entries.iter_mut().enumerate() {
        entry.entry_id = format!("BRK-{:04}", i + 1);
    }

    let mut severity_index: BTreeMap<&str, usize> = BTreeMap::new();
    for key in ["critical", "high", "medium", "low"] {
        severity_index.insert(key, 0);
    }
    for entry in &ledger_entries {
        *severity_index.get_mut(entry.severity.as_str()).unwrap() += 1;
    }

    let mut body = String::new();
    body.push_str("{\"ledger_entries\":[");
    for (i, f) in ledger_entries.iter().enumerate() {
        if i > 0 { body.push(','); }
        body.push_str(&format!(
            "{{\"entry_id\":\"{}\",\"control\":\"{}\",\"severity\":\"{}\",\"principal\":\"{}\",\"resource\":\"{}\",\"first_evidence\":\"{}\",\"evidence\":[{}],\"reason_codes\":[{}]}}",
            esc(&f.entry_id), esc(&f.control), esc(&f.severity), esc(&f.principal), esc(&f.resource), esc(&f.evidence[0]), json_arr(&f.evidence), json_arr(&f.reasons)
        ));
    }
    body.push_str(&format!(
        "],\"severity_index\":{{\"critical\":{},\"high\":{},\"medium\":{},\"low\":{}}}}}\n",
        severity_index["critical"], severity_index["high"], severity_index["medium"], severity_index["low"]
    ));
    if let Some(parent) = std::path::Path::new(&out_path).parent() {
        fs::create_dir_all(parent).unwrap();
    }
    fs::write(out_path, body).unwrap();
}

RS

cargo run --quiet
