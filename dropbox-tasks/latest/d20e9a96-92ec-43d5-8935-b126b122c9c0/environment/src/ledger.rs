use std::collections::BTreeMap;
use std::path::Path;

pub fn summarize(rows: &[crate::model::Row]) -> String {
    let total: usize = rows.iter().map(|r| r.bytes).sum();
    format!("{} rows, {} bytes", rows.len(), total)
}

pub fn stable_tag(repo: &str, name: &str) -> String {
    format!("{}::{}", repo.trim(), name.trim())
}

pub fn read_borrow_list(repo_root: &Path) -> Vec<String> {
    let path = repo_root.join("ledger/borrow.list");
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(str::to_string)
        .collect()
}

fn read_profile_map(profiles: &Path, repo: &str) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    let Ok(entries) = std::fs::read_dir(profiles) else {
        return out;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("conf") {
            continue;
        }
        let Ok(text) = std::fs::read_to_string(&path) else {
            continue;
        };
        let mut name = String::new();
        for line in text.lines() {
            let line = line.trim();
            if let Some(rest) = line.strip_prefix("name=") {
                name = rest.to_string();
            }
        }
        if name != repo {
            continue;
        }
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some((key, val)) = line.split_once('=') {
                out.insert(key.trim().to_string(), val.trim().to_string());
            }
        }
        break;
    }
    out
}

pub fn read_pool_order(profiles: &Path, repo: &str) -> Vec<String> {
    let map = read_profile_map(profiles, repo);
    map.get("pool_order")
        .map(|v| v.split(',').map(str::trim).filter(|s| !s.is_empty()).map(str::to_string).collect())
        .unwrap_or_else(|| vec!["pool-a.blob".to_string(), "pool-b.blob".to_string()])
}

pub fn read_scan_order(profiles: &Path, repo: &str) -> Vec<String> {
    let map = read_profile_map(profiles, repo);
    map.get("scan_order")
        .map(|v| v.split(',').map(str::trim).filter(|s| !s.is_empty()).map(str::to_string).collect())
        .unwrap_or_default()
}
