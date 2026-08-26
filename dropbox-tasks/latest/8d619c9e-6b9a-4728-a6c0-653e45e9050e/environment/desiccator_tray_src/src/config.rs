use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::types::TrayCfg;

pub fn load_config(path: &Path) -> Result<HashMap<String, TrayCfg>, ()> {
    let raw = fs::read_to_string(path).map_err(|_| ())?;
    let arr = extract_array(&raw, "trays").ok_or(())?;
    let mut out = HashMap::new();
    for block in split_objects(arr) {
        let tray_id = json_str(block, "tray_id").ok_or(())?;
        let capacity_units = json_int(block, "capacity_units").ok_or(())?;
        let tier = json_int(block, "tier").ok_or(())?;
        let regen_every = json_int(block, "regen_every").ok_or(())?;
        if tray_id.is_empty() || capacity_units <= 0 || tier <= 0 || regen_every <= 0 {
            return Err(());
        }
        out.insert(
            tray_id,
            TrayCfg {
                capacity_units,
                tier,
                regen_every,
            },
        );
    }
    if out.is_empty() {
        return Err(());
    }
    Ok(out)
}

fn extract_array<'a>(raw: &'a str, key: &str) -> Option<&'a str> {
    let needle = format!("\"{key}\"");
    let pos = raw.find(&needle)?;
    let after = &raw[pos + needle.len()..];
    let start = after.find('[')?;
    let mut depth = 0;
    for (i, ch) in after[start..].char_indices() {
        match ch {
            '[' => depth += 1,
            ']' => {
                depth -= 1;
                if depth == 0 {
                    return Some(&after[start..=start + i]);
                }
            }
            _ => {}
        }
    }
    None
}

fn split_objects(array_body: &str) -> Vec<&str> {
    let inner = array_body.trim().trim_start_matches('[').trim_end_matches(']');
    let mut out = Vec::new();
    let mut depth = 0;
    let mut start = None;
    for (i, ch) in inner.char_indices() {
        match ch {
            '{' => {
                if depth == 0 {
                    start = Some(i);
                }
                depth += 1;
            }
            '}' => {
                depth -= 1;
                if depth == 0 {
                    if let Some(s) = start {
                        out.push(&inner[s..=i]);
                    }
                }
            }
            _ => {}
        }
    }
    out
}

fn json_str(obj: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\"");
    let pos = obj.find(&needle)?;
    let after = &obj[pos + needle.len()..];
    let colon = after.find(':')?;
    parse_json_string(after[colon + 1..].trim())
}

fn json_int(obj: &str, key: &str) -> Option<i64> {
    let needle = format!("\"{key}\"");
    let pos = obj.find(&needle)?;
    let after = &obj[pos + needle.len()..];
    let colon = after.find(':')?;
    let val = after[colon + 1..].trim();
    let end = val.find(',').or_else(|| val.find('}')).unwrap_or(val.len());
    val[..end].trim().parse().ok()
}

fn parse_json_string(raw: &str) -> Option<String> {
    let t = raw.trim();
    if !t.starts_with('"') {
        return None;
    }
    let mut out = String::new();
    let mut escape = false;
    for ch in t[1..].chars() {
        if escape {
            out.push(ch);
            escape = false;
            continue;
        }
        if ch == '\\' {
            escape = true;
            continue;
        }
        if ch == '"' {
            return Some(out);
        }
        out.push(ch);
    }
    None
}
