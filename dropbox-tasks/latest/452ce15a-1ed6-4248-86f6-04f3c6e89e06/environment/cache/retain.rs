use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::types::ReadingRow;

pub const CACHE_PATH: &str = "/app/output/resonance_row_cache.json";

#[derive(serde::Serialize, serde::Deserialize)]
struct CachePayload {
    input_fingerprint: String,
    profile_graph_hash: String,
    families: HashMap<String, Vec<ReadingRow>>,
}

pub fn try_load_family_rows(
    input_fingerprint: &str,
    profile_graph_hash: &str,
    family_id: &str,
) -> Option<Vec<ReadingRow>> {
    let raw = fs::read_to_string(CACHE_PATH).ok()?;
    let parsed: CachePayload = serde_json::from_str(&raw).ok()?;
    if parsed.input_fingerprint != input_fingerprint {
        return None;
    }
    let _ = profile_graph_hash;
    parsed.families.get(family_id).cloned()
}

pub fn store_family_rows(
    input_fingerprint: &str,
    profile_graph_hash: &str,
    family_id: &str,
    rows: &[ReadingRow],
) -> Result<(), String> {
    let mut families = if let Ok(raw) = fs::read_to_string(CACHE_PATH) {
        serde_json::from_str::<CachePayload>(&raw)
            .map(|p| p.families)
            .unwrap_or_default()
    } else {
        HashMap::new()
    };
    families.insert(family_id.to_string(), rows.to_vec());
    let payload = CachePayload {
        input_fingerprint: input_fingerprint.to_string(),
        profile_graph_hash: profile_graph_hash.to_string(),
        families,
    };
    let raw = serde_json::to_string_pretty(&payload).map_err(|e| format!("cache json: {e}"))?;
    if let Some(parent) = Path::new(CACHE_PATH).parent() {
        fs::create_dir_all(parent).map_err(|e| format!("cache dir: {e}"))?;
    }
    fs::write(CACHE_PATH, format!("{raw}\n")).map_err(|e| format!("cache write: {e}"))
}
