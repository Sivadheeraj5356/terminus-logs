//! First-match preset policy.
use crate::boot_semantics::Semantics;
use crate::order_reader::Order;

pub fn resolve_action(unit: &str, order: &Order, sem: &Semantics) -> String {
    let mode = sem.decide_or("PRESET_MATCH", &["mode"], "last");
    let ignore_mode = sem.decide_or("PRESET_IGNORE", &["ignore"], "disable");
    let mut matches: Vec<String> = Vec::new();
    for (act, pat) in &order.presets {
        if pattern_match(pat, unit) {
            matches.push(act.clone());
            if mode == "first" {
                break;
            }
        }
    }
    let act = if mode == "last" {
        matches.last().cloned().unwrap_or_else(|| "unmatched".into())
    } else {
        matches.first().cloned().unwrap_or_else(|| "unmatched".into())
    };
    if act == "ignore" {
        if ignore_mode == "disable" { "disable".into() } else { "retain".into() }
    } else {
        act
    }
}

fn pattern_match(pat: &str, unit: &str) -> bool {
    if pat == "*" { return true; }
    if let Some(prefix) = pat.strip_suffix('*') {
        return unit.starts_with(prefix);
    }
    pat == unit
}
