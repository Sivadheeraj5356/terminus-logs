use std::collections::HashMap;
use std::env;
use std::fs;

#[derive(Clone)]
struct NamedValues {
    key: String,
    values: Vec<String>,
}

#[derive(Clone)]
struct Principal {
    id: String,
    tags: Vec<(String, String)>,
}

#[derive(Clone)]
struct Resource {
    id: String,
    tags: Vec<(String, String)>,
}

#[derive(Clone)]
struct Condition {
    op: String,
    key: String,
    values: Vec<String>,
    cidrs: Vec<(u32, u32)>,
}

#[derive(Clone)]
struct Statement {
    id: String,
    layer: String,
    allow: bool,
    principals: Vec<String>,
    actions: Vec<String>,
    resources: Vec<String>,
    conditions: Vec<usize>,
}

#[derive(Clone)]
struct Invariant {
    id: String,
    principals: Vec<String>,
    actions: Vec<String>,
    resources: Vec<String>,
    conditions: Vec<usize>,
}

struct Case {
    principals: Vec<Principal>,
    actions: Vec<String>,
    resources: Vec<Resource>,
    contexts: Vec<NamedValues>,
    session_tags: Vec<NamedValues>,
    conditions: Vec<Condition>,
    statements: [Vec<Statement>; 2],
    invariants: Vec<Invariant>,
    context_lookup: HashMap<String, usize>,
    session_lookup: HashMap<String, usize>,
}

#[derive(Clone, PartialEq)]
struct Decision {
    allowed: bool,
    deny_ids: Vec<String>,
    allow_ids: Vec<String>,
    missing_gate_layers: Vec<String>,
}

#[derive(Clone)]
struct RequestState {
    principal: usize,
    action: usize,
    resource: usize,
    context_values: Vec<usize>,
    session_values: Vec<Option<usize>>,
}

#[derive(Clone)]
struct Counterexample {
    request: RequestState,
    base: Decision,
    patched: Decision,
}

#[derive(Clone)]
struct InvariantHit {
    invariant_id: String,
    counterexample: Counterexample,
}

struct Report {
    classification: String,
    base_allow_count: i64,
    patched_allow_count: i64,
    regression_count: i64,
    blocked_count: i64,
    regression_counterexample: Option<Counterexample>,
    blocked_counterexample: Option<Counterexample>,
    violated_invariants: Vec<InvariantHit>,
}

fn parse_csv(token: &str) -> Vec<String> {
    if token == "-" {
        Vec::new()
    } else {
        token.split(',').map(|item| item.to_string()).collect()
    }
}

fn parse_tags(token: &str) -> Vec<(String, String)> {
    let mut tags = Vec::new();
    for item in parse_csv(token) {
        let (key, value) = item
            .split_once('=')
            .unwrap_or_else(|| panic!("invalid tag {}", item));
        tags.push((key.to_string(), value.to_string()));
    }
    tags
}

fn parse_ip(ip: &str) -> u32 {
    let parts: Vec<u32> = ip
        .split('.')
        .map(|part| part.parse::<u32>().unwrap_or_else(|_| panic!("invalid IPv4 {}", ip)))
        .collect();
    if parts.len() != 4 || parts.iter().any(|part| *part > 255) {
        panic!("invalid IPv4 {}", ip);
    }
    (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
}

fn parse_cidr(item: &str) -> (u32, u32) {
    let (ip, prefix_text) = item
        .split_once('/')
        .unwrap_or_else(|| panic!("invalid CIDR {}", item));
    let prefix = prefix_text
        .parse::<u32>()
        .unwrap_or_else(|_| panic!("invalid CIDR prefix {}", item));
    if prefix > 32 {
        panic!("invalid CIDR prefix {}", item);
    }
    let mask = if prefix == 0 { 0 } else { u32::MAX << (32 - prefix) };
    (parse_ip(ip) & mask, mask)
}

fn parse_case(path: &str) -> Case {
    let input = fs::read_to_string(path).unwrap_or_else(|e| panic!("cannot read {}: {}", path, e));
    let mut principals = Vec::new();
    let mut actions = Vec::new();
    let mut resources = Vec::new();
    let mut contexts = Vec::new();
    let mut session_tags = Vec::new();
    let mut conditions = Vec::new();
    let mut condition_lookup: HashMap<String, usize> = HashMap::new();
    let mut statements: [Vec<Statement>; 2] = [Vec::new(), Vec::new()];
    let mut invariants = Vec::new();

    for (line_no, raw) in input.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        match parts[0] {
            "PRINCIPAL" => {
                principals.push(Principal {
                    id: parts[1].to_string(),
                    tags: parse_tags(parts[2]),
                });
            }
            "ACTION" => actions.push(parts[1].to_string()),
            "RESOURCE" => {
                resources.push(Resource {
                    id: parts[1].to_string(),
                    tags: parse_tags(parts[3]),
                });
            }
            "CONTEXT" => {
                contexts.push(NamedValues {
                    key: parts[1].to_string(),
                    values: parse_csv(parts[2]),
                });
            }
            "SESSION_TAG" => {
                session_tags.push(NamedValues {
                    key: parts[1].to_string(),
                    values: parse_csv(parts[2]),
                });
            }
            "COND" => {
                let values = parse_csv(parts[4]);
                let cidrs = if parts[2] == "IpAddress" {
                    values.iter().map(|item| parse_cidr(item)).collect()
                } else {
                    Vec::new()
                };
                condition_lookup.insert(parts[1].to_string(), conditions.len());
                conditions.push(Condition {
                    op: parts[2].to_string(),
                    key: parts[3].to_string(),
                    values,
                    cidrs,
                });
            }
            "STMT" => {
                let bundle = match parts[1] {
                    "BASE" => 0,
                    "PATCHED" => 1,
                    other => panic!("line {}: invalid bundle {}", line_no + 1, other),
                };
                let condition_ids = parse_csv(parts[8])
                    .iter()
                    .map(|id| *condition_lookup.get(id).unwrap_or_else(|| panic!("unknown condition {}", id)))
                    .collect();
                statements[bundle].push(Statement {
                    id: parts[2].to_string(),
                    layer: parts[3].to_string(),
                    allow: match parts[4] {
                        "ALLOW" => true,
                        "DENY" => false,
                        other => panic!("line {}: invalid effect {}", line_no + 1, other),
                    },
                    principals: parse_csv(parts[5]),
                    actions: parse_csv(parts[6]),
                    resources: parse_csv(parts[7]),
                    conditions: condition_ids,
                });
            }
            "INVARIANT" => {
                let condition_ids = parse_csv(parts[5])
                    .iter()
                    .map(|id| *condition_lookup.get(id).unwrap_or_else(|| panic!("unknown condition {}", id)))
                    .collect();
                invariants.push(Invariant {
                    id: parts[1].to_string(),
                    principals: parse_csv(parts[2]),
                    actions: parse_csv(parts[3]),
                    resources: parse_csv(parts[4]),
                    conditions: condition_ids,
                });
            }
            other => panic!("line {}: unknown row {}", line_no + 1, other),
        }
    }

    let context_lookup = contexts
        .iter()
        .enumerate()
        .map(|(idx, item)| (item.key.clone(), idx))
        .collect();
    let session_lookup = session_tags
        .iter()
        .enumerate()
        .map(|(idx, item)| (item.key.clone(), idx))
        .collect();

    Case {
        principals,
        actions,
        resources,
        contexts,
        session_tags,
        conditions,
        statements,
        invariants,
        context_lookup,
        session_lookup,
    }
}

fn glob_match(pattern: &str, text: &str) -> bool {
    let p = pattern.as_bytes();
    let t = text.as_bytes();
    let mut dp = vec![vec![false; t.len() + 1]; p.len() + 1];
    dp[p.len()][t.len()] = true;
    for pi in (0..p.len()).rev() {
        for ti in (0..=t.len()).rev() {
            dp[pi][ti] = if p[pi] == b'*' {
                dp[pi + 1][ti] || (ti < t.len() && dp[pi][ti + 1])
            } else if p[pi] == b'?' {
                ti < t.len() && dp[pi + 1][ti + 1]
            } else {
                ti < t.len() && p[pi] == t[ti] && dp[pi + 1][ti + 1]
            };
        }
    }
    dp[0][0]
}

fn pattern_list_match(patterns: &[String], text: &str) -> bool {
    let mut has_positive = false;
    let mut positive_ok = false;
    for pattern in patterns {
        if let Some(negative) = pattern.strip_prefix('!') {
            if glob_match(negative, text) {
                return false;
            }
        } else {
            has_positive = true;
            if glob_match(pattern, text) {
                positive_ok = true;
            }
        }
    }
    positive_ok || !has_positive
}

fn tag_lookup<'a>(tags: &'a [(String, String)], key: &str) -> Option<&'a str> {
    tags.iter()
        .find_map(|(tag_key, tag_value)| if tag_key == key { Some(tag_value.as_str()) } else { None })
}

fn request_value<'a>(case: &'a Case, request: &'a RequestState, key: &str) -> Option<&'a str> {
    let (scope, name) = key
        .split_once('.')
        .unwrap_or_else(|| panic!("invalid condition key {}", key));
    match scope {
        "principal" => tag_lookup(&case.principals[request.principal].tags, name),
        "resource" => tag_lookup(&case.resources[request.resource].tags, name),
        "request" => case
            .context_lookup
            .get(name)
            .map(|idx| case.contexts[*idx].values[request.context_values[*idx]].as_str()),
        "session" => case.session_lookup.get(name).and_then(|idx| {
            request.session_values[*idx].map(|value_idx| case.session_tags[*idx].values[value_idx].as_str())
        }),
        _ => panic!("invalid condition scope {}", scope),
    }
}

fn condition_true(case: &Case, request: &RequestState, cond_idx: usize) -> bool {
    let condition = &case.conditions[cond_idx];
    let value = request_value(case, request, &condition.key);
    match condition.op.as_str() {
        "StringEquals" | "Bool" => value.is_some_and(|v| condition.values.iter().any(|item| item == v)),
        "StringNotEquals" => value.is_none_or(|v| !condition.values.iter().any(|item| item == v)),
        "StringLike" => value.is_some_and(|v| condition.values.iter().any(|pattern| glob_match(pattern, v))),
        "Null" => {
            let expect_null = condition.values[0] == "true";
            value.is_none() == expect_null
        }
        "IpAddress" => {
            let Some(value) = value else {
                return false;
            };
            let ip = parse_ip(value);
            condition.cidrs.iter().any(|(base, mask)| (ip & mask) == *base)
        }
        other => panic!("invalid condition op {}", other),
    }
}

fn conditions_true(case: &Case, request: &RequestState, conditions: &[usize]) -> bool {
    conditions.iter().all(|idx| condition_true(case, request, *idx))
}

fn statement_shape_match(case: &Case, request: &RequestState, statement: &Statement, check_conditions: bool) -> bool {
    pattern_list_match(&statement.principals, &case.principals[request.principal].id)
        && pattern_list_match(&statement.actions, &case.actions[request.action])
        && pattern_list_match(&statement.resources, &case.resources[request.resource].id)
        && (!check_conditions || conditions_true(case, request, &statement.conditions))
}

fn invariant_match(case: &Case, request: &RequestState, invariant: &Invariant) -> bool {
    pattern_list_match(&invariant.principals, &case.principals[request.principal].id)
        && pattern_list_match(&invariant.actions, &case.actions[request.action])
        && pattern_list_match(&invariant.resources, &case.resources[request.resource].id)
        && conditions_true(case, request, &invariant.conditions)
}

fn decision(case: &Case, bundle_idx: usize, request: &RequestState) -> Decision {
    let statements = &case.statements[bundle_idx];
    let mut deny_ids = Vec::new();
    let mut allow_ids = Vec::new();
    let mut identity_or_resource_allow = false;
    let mut boundary_allow = false;
    let mut scp_allow = false;
    let mut boundary_needed = false;
    let mut scp_needed = false;

    for statement in statements {
        if statement.layer == "BOUNDARY"
            && pattern_list_match(&statement.principals, &case.principals[request.principal].id)
        {
            boundary_needed = true;
        }
        if statement.layer == "SCP" && statement_shape_match(case, request, statement, false) {
            scp_needed = true;
        }
        if statement_shape_match(case, request, statement, true) {
            if statement.allow {
                allow_ids.push(statement.id.clone());
                if statement.layer == "IDENTITY" || statement.layer == "RESOURCE" {
                    identity_or_resource_allow = true;
                } else if statement.layer == "BOUNDARY" {
                    boundary_allow = true;
                } else if statement.layer == "SCP" {
                    scp_allow = true;
                }
            } else {
                deny_ids.push(statement.id.clone());
            }
        }
    }

    let mut missing_gate_layers = Vec::new();
    if boundary_needed && !boundary_allow {
        missing_gate_layers.push("BOUNDARY".to_string());
    }
    if scp_needed && !scp_allow {
        missing_gate_layers.push("SCP".to_string());
    }
    let allowed = deny_ids.is_empty()
        && identity_or_resource_allow
        && (!boundary_needed || boundary_allow)
        && (!scp_needed || scp_allow);

    Decision {
        allowed,
        deny_ids,
        allow_ids,
        missing_gate_layers,
    }
}

fn request_object_json(case: &Case, counterexample: &Counterexample) -> String {
    let request = &counterexample.request;
    let mut out = String::new();
    out.push('{');
    out.push_str(&format!(
        "\"principal_id\":\"{}\",\"action_id\":\"{}\",\"resource_id\":\"{}\",",
        escape_json(&case.principals[request.principal].id),
        escape_json(&case.actions[request.action]),
        escape_json(&case.resources[request.resource].id)
    ));
    out.push_str("\"request_context\":{");
    for (idx, context) in case.contexts.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str(&format!(
            "\"{}\":\"{}\"",
            escape_json(&context.key),
            escape_json(&context.values[request.context_values[idx]])
        ));
    }
    out.push_str("},\"session_tags\":{");
    let mut wrote = false;
    for (idx, tag) in case.session_tags.iter().enumerate() {
        if let Some(value_idx) = request.session_values[idx] {
            if wrote {
                out.push(',');
            }
            wrote = true;
            out.push_str(&format!("\"{}\":\"{}\"", escape_json(&tag.key), escape_json(&tag.values[value_idx])));
        }
    }
    out.push_str("},\"base_decision\":");
    out.push_str(&decision_json(&counterexample.base));
    out.push_str(",\"patched_decision\":");
    out.push_str(&decision_json(&counterexample.patched));
    out.push('}');
    out
}

fn enumerate_requests<F: FnMut(&RequestState)>(case: &Case, mut visit: F) {
    fn rec_session<F: FnMut(&RequestState)>(
        case: &Case,
        request: &mut RequestState,
        idx: usize,
        visit: &mut F,
    ) {
        if idx == case.session_tags.len() {
            visit(request);
            return;
        }
        request.session_values[idx] = None;
        rec_session(case, request, idx + 1, visit);
        for value_idx in 0..case.session_tags[idx].values.len() {
            request.session_values[idx] = Some(value_idx);
            rec_session(case, request, idx + 1, visit);
        }
    }

    fn rec_context<F: FnMut(&RequestState)>(
        case: &Case,
        request: &mut RequestState,
        idx: usize,
        visit: &mut F,
    ) {
        if idx == case.contexts.len() {
            rec_session(case, request, 0, visit);
            return;
        }
        for value_idx in 0..case.contexts[idx].values.len() {
            request.context_values[idx] = value_idx;
            rec_context(case, request, idx + 1, visit);
        }
    }

    let mut request = RequestState {
        principal: 0,
        action: 0,
        resource: 0,
        context_values: vec![0; case.contexts.len()],
        session_values: vec![None; case.session_tags.len()],
    };
    for principal in 0..case.principals.len() {
        request.principal = principal;
        for action in 0..case.actions.len() {
            request.action = action;
            for resource in 0..case.resources.len() {
                request.resource = resource;
                rec_context(case, &mut request, 0, &mut visit);
            }
        }
    }
}

fn solve(case: &Case) -> Report {
    let mut report = Report {
        classification: String::new(),
        base_allow_count: 0,
        patched_allow_count: 0,
        regression_count: 0,
        blocked_count: 0,
        regression_counterexample: None,
        blocked_counterexample: None,
        violated_invariants: Vec::new(),
    };
    let mut invariant_hits: Vec<Option<InvariantHit>> = vec![None; case.invariants.len()];

    enumerate_requests(case, |request| {
        let base = decision(case, 0, request);
        let patched = decision(case, 1, request);
        if base.allowed {
            report.base_allow_count += 1;
        }
        if patched.allowed {
            report.patched_allow_count += 1;
        }
        if !base.allowed && patched.allowed {
            report.regression_count += 1;
            if report.regression_counterexample.is_none() {
                report.regression_counterexample = Some(Counterexample {
                    request: request.clone(),
                    base: base.clone(),
                    patched: patched.clone(),
                });
            }
        }
        if base.allowed && !patched.allowed {
            report.blocked_count += 1;
            if report.blocked_counterexample.is_none() {
                report.blocked_counterexample = Some(Counterexample {
                    request: request.clone(),
                    base: base.clone(),
                    patched: patched.clone(),
                });
            }
        }
        if patched.allowed {
            for (idx, invariant) in case.invariants.iter().enumerate() {
                if invariant_hits[idx].is_none() && invariant_match(case, request, invariant) {
                    invariant_hits[idx] = Some(InvariantHit {
                        invariant_id: invariant.id.clone(),
                        counterexample: Counterexample {
                            request: request.clone(),
                            base: base.clone(),
                            patched: patched.clone(),
                        },
                    });
                }
            }
        }
    });

    report.violated_invariants = invariant_hits.into_iter().flatten().collect();
    let unsafe_policy = report.regression_count > 0 || !report.violated_invariants.is_empty();
    report.classification = if unsafe_policy && report.blocked_count > 0 {
        "mixed"
    } else if unsafe_policy {
        "regression"
    } else if report.blocked_count > 0 {
        "safer"
    } else {
        "equivalent"
    }
    .to_string();
    report
}

fn escape_json(text: &str) -> String {
    let mut out = String::new();
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(ch),
        }
    }
    out
}

fn string_list(items: &[String]) -> String {
    let mut out = String::from("[");
    for (idx, item) in items.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push('"');
        out.push_str(&escape_json(item));
        out.push('"');
    }
    out.push(']');
    out
}

fn decision_json(decision: &Decision) -> String {
    format!(
        "{{\"allowed\":{},\"matched_deny_statement_ids\":{},\"matched_allow_statement_ids\":{},\"missing_gate_layers\":{}}}",
        if decision.allowed { "true" } else { "false" },
        string_list(&decision.deny_ids),
        string_list(&decision.allow_ids),
        string_list(&decision.missing_gate_layers)
    )
}

fn report_json(case: &Case, report: &Report) -> String {
    let regression = report
        .regression_counterexample
        .as_ref()
        .map(|item| request_object_json(case, item))
        .unwrap_or_else(|| "null".to_string());
    let blocked = report
        .blocked_counterexample
        .as_ref()
        .map(|item| request_object_json(case, item))
        .unwrap_or_else(|| "null".to_string());

    let mut out = String::new();
    out.push_str("{\n");
    out.push_str(&format!("  \"classification\": \"{}\",\n", escape_json(&report.classification)));
    out.push_str(&format!("  \"base_allow_count\": {},\n", report.base_allow_count));
    out.push_str(&format!("  \"patched_allow_count\": {},\n", report.patched_allow_count));
    out.push_str(&format!("  \"regression_count\": {},\n", report.regression_count));
    out.push_str(&format!("  \"blocked_count\": {},\n", report.blocked_count));
    out.push_str(&format!("  \"regression_counterexample\": {},\n", regression));
    out.push_str(&format!("  \"blocked_counterexample\": {},\n", blocked));
    out.push_str("  \"violated_invariants\": [");
    for (idx, item) in report.violated_invariants.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str(&format!(
            "{{\"invariant_id\":\"{}\",\"counterexample\":{}}}",
            escape_json(&item.invariant_id),
            request_object_json(case, &item.counterexample)
        ));
    }
    out.push_str("]\n}\n");
    out
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        panic!("usage: analyzer <input_path> <output_path>");
    }
    let case = parse_case(&args[1]);
    let report = solve(&case);
    let json = report_json(&case, &report);
    fs::write(&args[2], json).unwrap_or_else(|e| panic!("cannot write {}: {}", args[2], e));
}
