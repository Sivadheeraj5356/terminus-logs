use std::fs;
use std::path::Path;

use crate::types::Manifest;

#[derive(Debug, Clone, serde::Deserialize)]
struct CacheRow {
    profile: String,
    width_ms: u64,
    manifest_gen: u32,
}

pub fn resolve_width(profile: &str, manifest: &Manifest) -> u64 {
    let path = Path::new("/app/environment/ops/sweep.cache");
    let raw = fs::read_to_string(path).unwrap_or_else(|_| "[]".into());
    let rows: Vec<CacheRow> = serde_json::from_str(&raw).unwrap_or_default();
    for row in rows {
        if row.profile == profile && row.manifest_gen > manifest.manifest_gen {
            return row.width_ms;
        }
    }
    manifest.window_width_ms
}
