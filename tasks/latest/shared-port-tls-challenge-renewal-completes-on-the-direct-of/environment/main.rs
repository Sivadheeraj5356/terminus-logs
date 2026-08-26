use std::fs;
use std::path::Path;
use std::process;

use pathlab::ingest::lab_drv::build_report;
use pathlab::seg::wal::ensure_var_dir;

fn main() {
    ensure_var_dir();
    let env_root = Path::new("/app/environment");
    let out = Path::new("/app/output/lab_observations.json");
    let (report, _journal) = build_report(env_root);
    if let Some(parent) = out.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let body = serde_json::to_string_pretty(&report).unwrap_or_else(|_| "{}".into());
    if fs::write(out, format!("{body}\n")).is_err() {
        process::exit(1);
    }
}
