use crate::types::{CheckState, ContractError, Model};
use crate::util::{parse_canonical_i32, valid_identifier};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
struct Violation {
    priority: u8,
    line: usize,
    token: &'static str,
}

#[derive(Clone)]
struct Snapshot {
    point: BTreeMap<String, i32>,
    locked: BTreeSet<String>,
    budget: i32,
}

fn push(v: &mut Vec<Violation>, priority: u8, line: usize, token: &'static str) {
    v.push(Violation { priority, line, token });
}

pub fn parse_audit(text: &str, model: &Model) -> Result<Vec<CheckState>, ContractError> {
    let mut violations = Vec::<Violation>::new();
    let mut first_record = true;
    let mut seen_header = false;
    let mut non_comment = 0usize;
    let mut sessions = BTreeSet::<String>::new();
    let mut checks = BTreeSet::<String>::new();
    let mut current_session: Option<String> = None;
    let mut session_line = 1usize;
    let mut expect_point = false;
    let mut have_point = false;
    let mut point = BTreeMap::<String, i32>::new();
    let mut locked = BTreeSet::<String>::new();
    let mut budget = 0i32;
    let mut stack = Vec::<Snapshot>::new();
    let mut results = Vec::<CheckState>::new();

    for (index, raw) in text.lines().enumerate() {
        let line = index + 1;
        if raw.is_empty() || raw.starts_with('#') {
            continue;
        }
        non_comment += 1;
        let fields: Vec<&str> = raw.split('|').collect();
        let kind = fields[0];

        if first_record {
            first_record = false;
            if fields.as_slice() != ["AUDIT", "1"] {
                push(&mut violations, 1, line, "E_AUDIT_HEADER");
            } else {
                seen_header = true;
                continue;
            }
        } else if kind == "AUDIT" {
            push(&mut violations, 1, line, "E_AUDIT_HEADER");
            continue;
        }

        if expect_point && kind != "POINT" {
            push(&mut violations, 8, session_line, "E_AUDIT_STATE");
            expect_point = false;
        }

        match kind {
            "SESSION" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) {
                    push(&mut violations, 3, line, "E_AUDIT_IDENTIFIER");
                    continue;
                }
                if current_session.is_some() {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
                let id = fields[1].to_string();
                if !sessions.insert(id.clone()) {
                    push(&mut violations, 5, line, "E_AUDIT_DUPLICATE");
                }
                current_session = Some(id);
                session_line = line;
                expect_point = true;
                have_point = false;
                point.clear();
                locked.clear();
                budget = 0;
                stack.clear();
            }
            "POINT" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if current_session.is_none() || !expect_point || have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
                expect_point = false;
                let mut parsed = BTreeMap::<String, i32>::new();
                if fields[1].is_empty() {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                } else {
                    for assignment in fields[1].split(',') {
                        let mut parts = assignment.split('=');
                        let feature = parts.next().unwrap_or("");
                        let value_text = parts.next().unwrap_or("");
                        if parts.next().is_some() || feature.is_empty() || value_text.is_empty() {
                            push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                            continue;
                        }
                        if !valid_identifier(feature) {
                            push(&mut violations, 3, line, "E_AUDIT_IDENTIFIER");
                            continue;
                        }
                        let Some(value) = parse_canonical_i32(value_text) else {
                            push(&mut violations, 4, line, "E_AUDIT_NUMBER");
                            continue;
                        };
                        if parsed.insert(feature.to_string(), value).is_some() {
                            push(&mut violations, 5, line, "E_AUDIT_DUPLICATE");
                        }
                        let Some(spec) = model.features.get(feature) else {
                            push(&mut violations, 6, line, "E_AUDIT_REFERENCE");
                            continue;
                        };
                        if value < spec.min || value > spec.max {
                            push(&mut violations, 7, line, "E_AUDIT_RANGE");
                        }
                    }
                }
                if parsed.len() != model.features.len()
                    || model.features.keys().any(|feature| !parsed.contains_key(feature))
                {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
                point = parsed;
                have_point = true;
            }
            "PUSH" => {
                if fields.len() != 1 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if current_session.is_none() || !have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                } else {
                    stack.push(Snapshot { point: point.clone(), locked: BTreeSet::new(), budget: 0 });
                    if stack.len() > 8 {
                        push(&mut violations, 9, line, "E_AUDIT_LIMIT");
                    }
                }
            }
            "POP" => {
                if fields.len() != 1 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if current_session.is_none() || !have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                } else if let Some(snapshot) = stack.pop() {
                    point = snapshot.point;
                    locked = snapshot.locked;
                    budget = snapshot.budget;
                } else {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
            }
            "SET" => {
                if fields.len() != 3 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) {
                    push(&mut violations, 3, line, "E_AUDIT_IDENTIFIER");
                    continue;
                }
                let Some(value) = parse_canonical_i32(fields[2]) else {
                    push(&mut violations, 4, line, "E_AUDIT_NUMBER");
                    continue;
                };
                let Some(spec) = model.features.get(fields[1]) else {
                    push(&mut violations, 6, line, "E_AUDIT_REFERENCE");
                    continue;
                };
                if value < spec.min || value > spec.max {
                    push(&mut violations, 7, line, "E_AUDIT_RANGE");
                }
                if current_session.is_none() || !have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                } else {
                    point.insert(fields[1].to_string(), value);
                }
            }
            "LOCK" | "UNLOCK" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) {
                    push(&mut violations, 3, line, "E_AUDIT_IDENTIFIER");
                    continue;
                }
                if !model.features.contains_key(fields[1]) {
                    push(&mut violations, 6, line, "E_AUDIT_REFERENCE");
                    continue;
                }
                if current_session.is_none() || !have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                } else if kind == "LOCK" {
                    locked.insert(fields[1].to_string());
                } else {
                    let _ = fields[1];
                }
            }
            "BUDGET" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                let Some(value) = parse_canonical_i32(fields[1]) else {
                    push(&mut violations, 4, line, "E_AUDIT_NUMBER");
                    continue;
                };
                if !(0..=500).contains(&value) {
                    push(&mut violations, 7, line, "E_AUDIT_RANGE");
                }
                if current_session.is_none() || !have_point {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                } else {
                    budget = value;
                }
            }
            "CHECK" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) {
                    push(&mut violations, 3, line, "E_AUDIT_IDENTIFIER");
                    continue;
                }
                let id = fields[1].to_string();
                if !checks.insert(id.clone()) {
                    push(&mut violations, 5, line, "E_AUDIT_DUPLICATE");
                }
                if let Some(session) = current_session.as_ref().filter(|_| have_point) {
                    results.push(CheckState {
                        session: session.clone(),
                        check: id,
                        budget,
                        point: point.clone(),
                        locked: locked.clone(),
                    });
                } else {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
            }
            "END" => {
                if fields.len() != 1 {
                    push(&mut violations, 2, line, "E_AUDIT_FIELDS");
                    continue;
                }
                if current_session.is_none() || !have_point || !stack.is_empty() {
                    push(&mut violations, 8, line, "E_AUDIT_STATE");
                }
                current_session = None;
                expect_point = false;
                have_point = false;
                point.clear();
                locked.clear();
                stack.clear();
                budget = 0;
            }
            _ => push(&mut violations, 2, line, "E_AUDIT_FIELDS"),
        }
    }

    if non_comment == 0 || !seen_header {
        push(&mut violations, 1, 1, "E_AUDIT_HEADER");
    }
    if expect_point {
        push(&mut violations, 8, session_line, "E_AUDIT_STATE");
    }
    if current_session.is_some() {
        push(&mut violations, 8, text.lines().count().max(1), "E_AUDIT_STATE");
    }
    if sessions.len() > 12 || results.len() > 40 || non_comment > 200 {
        push(&mut violations, 9, 1, "E_AUDIT_LIMIT");
    }

    if let Some(winner) = violations.iter().min_by_key(|v| (v.priority, v.line)) {
        return Err(ContractError { token: winner.token, line: winner.line });
    }
    Ok(results)
}
