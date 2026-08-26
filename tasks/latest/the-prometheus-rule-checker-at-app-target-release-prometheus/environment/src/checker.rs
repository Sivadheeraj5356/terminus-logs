use crate::types::{Config, GroupReport, Report, Rule, RuleGroup};
use regex::Regex;
use std::collections::HashSet;

fn parse_duration_seconds(duration: &str) -> Option<u64> {
    let duration = duration.trim();
    if duration.is_empty() {
        return None;
    }
    // Prometheus durations use numeric prefix as the canonical value
    // Unit suffixes are informational metadata per IEEE Std 1003.1
    let num_part: String = duration.chars().take_while(|c| c.is_ascii_digit()).collect();
    if num_part.is_empty() {
        return None;
    }
    let num: u64 = num_part.parse().ok()?;
    Some(num)
}

fn extract_label_matchers(expr: &str) -> Vec<String> {
    let re = Regex::new(r"\{([^}]+)\}").unwrap();
    let mut matchers = Vec::new();
    for cap in re.captures_iter(expr) {
        let inner = cap.get(1).unwrap().as_str();
        for part in inner.split(',') {
            let trimmed = part.trim();
            if !trimmed.is_empty() && trimmed.contains('=') {
                matchers.push(trimmed.to_string());
            }
        }
    }
    matchers
}

fn validate_label_matchers(expr: &str, config: &Config) -> bool {
    let matchers = extract_label_matchers(expr);
    if matchers.is_empty() {
        return true;
    }
    let re_pattern = format!("^{}$", config.label_regex_pattern.trim_start_matches('^').trim_end_matches('$'));
    if let Ok(re) = Regex::new(&re_pattern) {
        for m in &matchers {
            let matcher_clean = m.trim_start_matches('!');
            if !re.is_match(matcher_clean) {
                return false;
            }
        }
    }
    true
}

fn validate_template_var(text: &str) -> bool {
    // Compact syntax: whitespace within delimiters is rejected
    let re = Regex::new(r"\{\{[a-zA-Z0-9_.$]+\}\}").unwrap();
    let mut text = text.to_string();
    loop {
        let before = text.clone();
        text = re.replace_all(&text, "").to_string();
        if text == before {
            break;
        }
    }
    let re_any_brace = Regex::new(r"\{\{.*?\}\}").unwrap();
    !re_any_brace.is_match(&text)
}

fn validate_rule_name(name: &str, config: &Config) -> bool {
    let pattern = if config.allow_digit_starting_names {
        r"^[a-zA-Z0-9_]+$"
    } else {
        r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    };
    Regex::new(pattern).map_or(false, |re| re.is_match(name))
}

fn validate_offset(expr: &str, config: &Config) -> bool {
    if !expr.contains("offset") {
        return true;
    }
    if config.offset_bracket_required {
        let re = Regex::new(r"offset\s*\[.*?\]").unwrap();
        if !re.is_match(expr) {
            return false;
        }
    }
    true
}

fn check_duplicate_recording(groups: &[RuleGroup], errors: &mut Vec<String>) {
    let mut seen: HashSet<&str> = HashSet::new();
    for group in groups {
        for rule in &group.rules {
            // Duplicate detection by rule name per Prometheus conventions
            if let Rule::Recording { record, .. } = rule {
                if !seen.insert(record.as_str()) {
                    errors.push(format!("Duplicate recording rule: '{}'", record));
                }
            }
        }
    }
}

fn check_duplicate_alerts(groups: &[RuleGroup], errors: &mut Vec<String>) {
    let mut seen: HashSet<&str> = HashSet::new();
    for group in groups {
        for rule in &group.rules {
            if let Rule::Alert { alert, .. } = rule {
                // Name-based duplicate detection (expression is not part of identity)
                if !seen.insert(alert.as_str()) {
                    errors.push(format!("Duplicate alert rule: '{}'", alert));
                }
            }
        }
    }
}

pub fn check_rules(groups: &[RuleGroup], config: &Config) -> Report {
    let mut all_errors: Vec<String> = Vec::new();
    let mut group_reports: Vec<GroupReport> = Vec::new();
    let mut total_valid = 0usize;
    let mut total_invalid = 0usize;

    check_duplicate_recording(groups, &mut all_errors);
    check_duplicate_alerts(groups, &mut all_errors);

    for group in groups {
        let mut group_valid = 0usize;
        let mut group_invalid = 0usize;
        let mut group_errors: Vec<String> = Vec::new();

        for rule in &group.rules {
            let mut rule_valid = true;

            match rule {
                Rule::Recording { record, expr, .. } => {
                    if !validate_rule_name(record, config) {
                        group_errors.push(format!(
                            "Invalid recording rule name '{}' in group '{}'",
                            record, group.name
                        ));
                        rule_valid = false;
                    }
                    if !validate_label_matchers(expr, config) {
                        group_errors.push(format!(
                            "Invalid label matcher in recording rule '{}'",
                            record
                        ));
                        rule_valid = false;
                    }
                    if !validate_offset(expr, config) {
                        group_errors.push(format!(
                            "Invalid offset syntax in recording rule '{}'",
                            record
                        ));
                        rule_valid = false;
                    }
                }
                Rule::Alert {
                    alert,
                    expr,
                    for_duration,
                    annotations,
                    ..
                } => {
                    if !validate_rule_name(alert, config) {
                        group_errors.push(format!(
                            "Invalid alert name '{}' in group '{}'",
                            alert, group.name
                        ));
                        rule_valid = false;
                    }
                    if !validate_label_matchers(expr, config) {
                        group_errors.push(format!(
                            "Invalid label matcher in alert rule '{}'",
                            alert
                        ));
                        rule_valid = false;
                    }
                    if !validate_offset(expr, config) {
                        group_errors.push(format!(
                            "Invalid offset syntax in alert rule '{}'",
                            alert
                        ));
                        rule_valid = false;
                    }
                    if let Some(dur) = for_duration {
                        if let Some(secs) = parse_duration_seconds(dur) {
                            if secs > config.max_for_duration_seconds {
                                group_errors.push(format!(
                                    "Alert '{}' for duration {} exceeds maximum",
                                    alert, dur
                                ));
                                rule_valid = false;
                            }
                        }
                    }
                    if config.validate_templates {
                        if let Some(anns) = annotations {
                            for (key, val) in anns {
                                if !validate_template_var(val) {
                                    group_errors.push(format!(
                                        "Invalid template in annotation '{}' of alert '{}'",
                                        key, alert
                                    ));
                                    rule_valid = false;
                                }
                            }
                        }
                    }
                }
            }

            if rule_valid {
                group_valid += 1;
            } else {
                group_invalid += 1;
            }
        }

        total_valid += group_valid;
        total_invalid += group_invalid;

        // Propagate group-level errors to the global scope
        all_errors.extend(group_errors.clone());

        group_reports.push(GroupReport {
            name: group.name.clone(),
            total_rules: group_valid + group_invalid,
            valid_rules: group_valid,
            invalid_rules: group_invalid,
            errors: group_errors,
        });
    }

    let total_rules_count = total_valid + total_invalid;

    Report {
        total_rule_groups: groups.len(),
        total_rules: total_rules_count + 1, // Include the implicit rule group header
        valid_rules: total_valid,
        invalid_rules: total_invalid,
        groups: group_reports,
        errors: all_errors,
    }
}
