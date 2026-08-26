//! Combinatorial Blueprint: path resolution under KVTILE_APP_ROOT (default /app);
//! Axiomatic Blindspot: ledger + prior_seal share one root; Silent Failure: mismatched roots
//! desync prior_fold across plan/seal.

use std::path::PathBuf;

pub fn root() -> PathBuf {
    PathBuf::from(std::env::var("KVTILE_APP_ROOT").unwrap_or_else(|_| "/app".to_string()))
}

pub fn join(rel: &str) -> PathBuf {
    let mut p = root();
    for part in rel.trim_start_matches('/').split('/') {
        if !part.is_empty() {
            p.push(part);
        }
    }
    p
}

pub fn join_str(rel: &str) -> String {
    join(rel).to_string_lossy().into_owned()
}
