use crate::pack_fold_k::fold_k;
use crate::pack_mix_k9::fingerprint;
use crate::wal;
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub fn emit_report(out: &Path) -> bool {
    let state_dir = Path::new("/app/desk-state");
    if !crate::engine::all_epoch_caches_present(state_dir, 3) {
        return false;
    }
    if !crate::engine::checkpoint_ready(state_dir) {
        return false;
    }
    if !wal::wal_crc_chain_intact(state_dir) {
        return false;
    }
    let rows = load_epochs(state_dir);
    let (left, right): (Vec<Value>, Vec<Value>) = rows.into_iter().partition(|row| {
        matches!(
            row.get("phase").and_then(|v| v.as_str()),
            Some("sr5") | Some("sk8")
        )
    });
    let folded = fold_k(&left, &right);
    let bundle = json!({
        "rows": folded,
        "chain_fingerprint": fingerprint(&folded),
    });
    if let Some(parent) = out.parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::write(out, serde_json::to_string_pretty(&bundle).unwrap() + "\n").is_ok()
}

fn load_epochs(state_dir: &Path) -> Vec<Value> {
    let mut ids: Vec<u32> = Vec::new();
    if let Ok(entries) = fs::read_dir(state_dir) {
        for ent in entries.flatten() {
            let name = ent.file_name().to_string_lossy().into_owned();
            if let Some(rest) = name.strip_prefix("epoch_") {
                if let Some(stem) = rest.strip_suffix(".json") {
                    if let Ok(n) = stem.parse::<u32>() {
                        ids.push(n);
                    }
                }
            }
        }
    }
    ids.sort_unstable();
    let mut rows = Vec::new();
    for id in ids {
        let cache = state_dir.join(format!("epoch_{id}.json"));
        let chunk: Vec<Value> =
            serde_json::from_str(&fs::read_to_string(&cache).unwrap_or_default()).unwrap_or_default();
        rows.extend(chunk);
    }
    rows
}
