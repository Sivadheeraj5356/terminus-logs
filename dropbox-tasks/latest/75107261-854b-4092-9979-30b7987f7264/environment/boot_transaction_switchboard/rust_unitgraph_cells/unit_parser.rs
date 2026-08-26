//! Closed unit-file grammar for supported sections.
use std::collections::BTreeMap;

use crate::reconcile_failure;

#[derive(Clone, Debug, Default)]
pub struct ParsedUnit {
    pub sections: BTreeMap<String, BTreeMap<String, Vec<String>>>,
}

pub fn parse(text: &str) -> Result<ParsedUnit, i32> {
    let mut cur = String::new();
    let mut sections: BTreeMap<String, BTreeMap<String, Vec<String>>> = BTreeMap::new();
    let mut pending = String::new();
    for raw_line in text.lines() {
        let mut line = if pending.is_empty() {
            raw_line.to_string()
        } else {
            let mut s = pending.clone();
            s.push_str(raw_line);
            pending.clear();
            s
        };
        if line.ends_with('\\') {
            line.pop();
            pending = line;
            continue;
        }
        let line = line.trim_end();
        if line.is_empty() || line.starts_with('#') || line.starts_with(';') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            cur = line[1..line.len()-1].to_string();
            if !matches!(cur.as_str(), "Unit"|"Install"|"Service"|"Mount"|"Automount"|"Path"|"Target") {
                return Err(err("bad section"));
            }
            sections.entry(cur.clone()).or_default();
            continue;
        }
        if cur.is_empty() {
            return Err(err("directive outside section"));
        }
        let (k, v) = split_assign(line)?;
        let slot = sections.entry(cur.clone()).or_default().entry(k).or_default();
        if v.is_empty() {
            // empty assignment — caller/merger interprets reset
            slot.clear();
            slot.push(String::new());
        } else {
            // if last was empty reset marker alone, start fresh
            if slot.len() == 1 && slot[0].is_empty() {
                slot.clear();
            }
            slot.push(unquote(&v));
        }
    }
    if !pending.is_empty() {
        return Err(err("dangling continuation"));
    }
    Ok(ParsedUnit { sections })
}

fn split_assign(line: &str) -> Result<(String, String), i32> {
    let (k, v) = line.split_once('=').ok_or_else(|| err("missing ="))?;
    if k.is_empty() { return Err(err("empty key")); }
    Ok((k.to_string(), v.to_string()))
}

fn unquote(v: &str) -> String {
    if v.len() >= 2 && v.starts_with('"') && v.ends_with('"') {
        v[1..v.len()-1].replace("\\\"", "\"").replace("\\\\", "\\")
    } else {
        v.to_string()
    }
}

fn err(msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, msg);
    reconcile_failure::EXIT_UNIT_LOADING
}

pub fn get_list(u: &ParsedUnit, section: &str, key: &str) -> Vec<String> {
    u.sections.get(section).and_then(|s| s.get(key)).cloned().unwrap_or_default()
        .into_iter().filter(|x| !x.is_empty()).collect()
}

pub fn get_scalar(u: &ParsedUnit, section: &str, key: &str) -> Option<String> {
    u.sections.get(section).and_then(|s| s.get(key)).and_then(|v| v.last().cloned()).filter(|x| !x.is_empty())
}
