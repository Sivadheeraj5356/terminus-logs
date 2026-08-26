//! Offline unit/map catalog helpers for editorial tooling.

use serde_json::Value;
use std::fs;
use std::path::Path;

pub fn list_json_names(dir: &Path) -> Vec<String> {
    let mut names = Vec::new();
    let Ok(rd) = fs::read_dir(dir) else {
        return names;
    };
    for ent in rd.flatten() {
        let p = ent.path();
        if p.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Some(stem) = p.file_stem().and_then(|s| s.to_str()) {
                names.push(stem.to_string());
            }
        }
    }
    names.sort();
    names
}

pub fn load_value(path: &Path) -> Option<Value> {
    let raw = fs::read_to_string(path).ok()?;
    serde_json::from_str(&raw).ok()
}
