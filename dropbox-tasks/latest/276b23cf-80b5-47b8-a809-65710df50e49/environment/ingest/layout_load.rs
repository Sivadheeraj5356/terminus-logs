use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

pub fn scan_sections(text: &str, header: &str) -> Vec<BTreeMap<String, String>> {
    let mut rows: Vec<BTreeMap<String, String>> = Vec::new();
    let mut block: BTreeMap<String, String> = BTreeMap::new();
    let mut active = false;
    for raw in text.lines() {
        let line = raw.trim();
        if line == header {
            if !block.is_empty() {
                rows.push(block);
            }
            block = BTreeMap::new();
            active = true;
            continue;
        }
        if line.starts_with("[[") && active {
            if !block.is_empty() {
                rows.push(block);
            }
            block = BTreeMap::new();
            active = line == header;
            continue;
        }
        if active && line.contains('=') && !line.starts_with('[') && !line.starts_with('#') {
            let (key, val) = line.split_once('=').unwrap_or(("", ""));
            let key = key.trim().to_string();
            let val = val.trim().trim_matches('"').to_string();
            block.insert(key, val);
        }
    }
    if active && !block.is_empty() {
        rows.push(block);
    }
    rows
}

pub fn load_muxes(data: &Path) -> Vec<BTreeMap<String, String>> {
    let text = fs::read_to_string(data.join("mux_layout.toml")).unwrap_or_default();
    scan_sections(&text, "[[mux]]")
}

pub fn load_lanes(data: &Path) -> Vec<BTreeMap<String, String>> {
    let text = fs::read_to_string(data.join("lane_layout.toml")).unwrap_or_default();
    scan_sections(&text, "[[lane]]")
}

pub fn load_rows(data: &Path) -> Vec<BTreeMap<String, String>> {
    let text = fs::read_to_string(data.join("layout_t9.toml")).unwrap_or_default();
    scan_sections(&text, "[[row]]")
}

pub fn load_policy(data: &Path) -> Vec<BTreeMap<String, String>> {
    let text = fs::read_to_string(data.join("cohort_policy.toml")).unwrap_or_default();
    scan_sections(&text, "[[plan]]")
}

pub fn load_arm_dispatch(data: &Path) -> Vec<BTreeMap<String, String>> {
    let text = fs::read_to_string(data.join("arm_dispatch.toml")).unwrap_or_default();
    scan_sections(&text, "[[dispatch]]")
}

fn load_kv_section(data: &Path, file: &str, section: &str) -> std::collections::HashMap<String, String> {
    let text = fs::read_to_string(data.join(file)).unwrap_or_default();
    let mut out = std::collections::HashMap::new();
    let mut in_section = false;
    for raw in text.lines() {
        let line = raw.trim();
        if line == format!("[{section}]") {
            in_section = true;
            continue;
        }
        if line.starts_with('[') {
            in_section = false;
            continue;
        }
        if in_section && line.contains('=') {
            let (key, val) = line.split_once('=').unwrap_or(("", ""));
            out.insert(key.trim().to_string(), val.trim().trim_matches('"').to_string());
        }
    }
    out
}

pub fn load_plan_manifest(data: &Path) -> std::collections::HashMap<String, String> {
    load_kv_section(data, "plan_manifest.toml", "plan_hash")
}

pub fn load_seal_manifest(data: &Path) -> std::collections::HashMap<String, String> {
    load_kv_section(data, "seal_manifest.toml", "observation_seal")
}

pub fn load_alpn_rules(data: &Path) -> std::collections::HashMap<String, String> {
    load_kv_section(data, "alpn_rules.toml", "alpn")
}

pub fn load_epoch_map(data: &Path) -> std::collections::HashMap<String, u32> {
    let rows = scan_sections(
        &fs::read_to_string(data.join("epoch_map.toml")).unwrap_or_default(),
        "[[epoch]]",
    );
    let mut out = std::collections::HashMap::new();
    for row in rows {
        if let (Some(slot), Some(value)) = (row.get("slot"), row.get("value")) {
            if let Ok(epoch) = value.parse::<u32>() {
                out.insert(slot.clone(), epoch);
            }
        }
    }
    out
}

pub fn load_alpn_codes(data: &Path) -> std::collections::HashMap<String, u32> {
    let rows = scan_sections(
        &fs::read_to_string(data.join("alpn_codes.toml")).unwrap_or_default(),
        "[[code]]",
    );
    let mut out = std::collections::HashMap::new();
    for row in rows {
        if let (Some(name), Some(value)) = (row.get("name"), row.get("value")) {
            if let Ok(code) = value.parse::<u32>() {
                out.insert(name.clone(), code);
            }
        }
    }
    out
}

pub fn load_wal_manifest(data: &Path) -> std::collections::HashMap<String, String> {
    let mut out = load_kv_section(data, "wal_manifest.toml", "wal");
    out.extend(load_kv_section(data, "wal_manifest.toml", "wal.recover"));
    out.extend(load_kv_section(data, "wal_manifest.toml", "wal.reconcile"));
    out.extend(load_kv_section(data, "wal_manifest.toml", "wal.journal_chain"));
    out
}

pub fn load_epoch_bind(data: &Path) -> std::collections::HashMap<String, String> {
    load_kv_section(data, "epoch_bind.toml", "remote")
}

pub fn load_policy_revision(data: &Path) -> String {
    load_kv_section(data, "cohort_policy.toml", "meta")
        .get("policy_revision")
        .cloned()
        .unwrap_or_default()
}

pub fn load_strip_rules(data: &Path) -> std::collections::HashMap<String, String> {
    let text = fs::read_to_string(data.join("strip_rules.toml")).unwrap_or_default();
    let mut out = std::collections::HashMap::new();
    let mut in_section = false;
    for raw in text.lines() {
        let line = raw.trim();
        if line == "[strip]" {
            in_section = true;
            continue;
        }
        if line.starts_with('[') {
            in_section = false;
            continue;
        }
        if in_section && line.contains('=') {
            let (key, val) = line.split_once('=').unwrap_or(("", ""));
            out.insert(key.trim().to_string(), val.trim().trim_matches('"').to_string());
        }
    }
    out
}

pub fn rows_to_maps(
    rows: &[BTreeMap<String, String>],
) -> std::collections::HashMap<String, std::collections::HashMap<String, String>> {
    let mut out = std::collections::HashMap::new();
    for row in rows {
        if let Some(id) = row.get("mux_id") {
            out.insert(id.clone(), row.iter().map(|(k, v)| (k.clone(), v.clone())).collect());
        }
    }
    out
}

pub fn lanes_to_maps(
    rows: &[BTreeMap<String, String>],
) -> std::collections::HashMap<String, std::collections::HashMap<String, String>> {
    let mut out = std::collections::HashMap::new();
    for row in rows {
        if let Some(id) = row.get("lane_id") {
            out.insert(id.clone(), row.iter().map(|(k, v)| (k.clone(), v.clone())).collect());
        }
    }
    out
}

pub fn dispatch_to_map(
    rows: &[BTreeMap<String, String>],
) -> std::collections::HashMap<String, String> {
    let mut out = std::collections::HashMap::new();
    for row in rows {
        if let (Some(id), Some(arm)) = (row.get("dispatch_id"), row.get("material_arm")) {
            out.insert(id.clone(), arm.clone());
        }
    }
    out
}
