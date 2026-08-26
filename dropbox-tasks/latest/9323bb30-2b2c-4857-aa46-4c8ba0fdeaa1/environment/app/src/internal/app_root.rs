//! Combinatorial Blueprint: path resolution under KVTILE_APP_ROOT (default /app);
//! Axiomatic Blindspot: ledger + prior_seal share one root; Silent Failure: mismatched roots
//! desync prior_fold across plan/seal.

use std::path::PathBuf;

pub fn root() -> PathBuf {
    unimplemented!("app_root::root — resolve KVTILE_APP_ROOT or /app per /app/docs/runtime-env.md")
}

pub fn join(_rel: &str) -> PathBuf {
    unimplemented!("app_root::join — join relative path under root()")
}

pub fn join_str(_rel: &str) -> String {
    unimplemented!("app_root::join_str — string form of join()")
}
