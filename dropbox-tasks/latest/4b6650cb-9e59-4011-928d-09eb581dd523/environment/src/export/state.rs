use std::fs;
use std::path::Path;

use crate::types::{Manifest, ScopeRecord, ScopeState};

pub fn write_scope_state(
    _profile: &str,
    manifest: &Manifest,
    records: &[ScopeRecord],
    _bound_rotate: u32,
) {
    let last = records.iter().map(|r| r.rotate_gen).min().unwrap_or(0);
    let state = ScopeState {
        manifest_gen: manifest.manifest_gen,
        scope_count: records.len() as u32,
        last_rotate_gen: last,
    };
    let dir = Path::new("/app/state");
    fs::create_dir_all(dir).ok();
    let json = serde_json::to_string_pretty(&state).expect("state json");
    fs::write(dir.join("scope_state.json"), json).expect("write state");
}
