use crate::recovery::replay_with_recovery;
use crate::report::build_report;
use std::fs;
use std::path::PathBuf;

pub fn run(events_path: &str, log_path: &str, report_path: Option<&str>) -> Result<(), String> {
    if PathBuf::from(log_path).exists() {
        fs::remove_file(log_path).ok();
    }
    let (ledger, rollback) = replay_with_recovery(
        events_path,
        "/app/data/rams",
        "/app/snapshot/compactor_anchor.json",
        log_path,
    )?;
    if let Some(path) = report_path {
        let body = build_report(&ledger, rollback, count_guide_mark(log_path)?);
        fs::write(path, serde_json::to_string_pretty(&body).unwrap() + "\n")
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn count_guide_mark(log_path: &str) -> Result<u32, String> {
    let text = fs::read_to_string(log_path).map_err(|e| e.to_string())?;
    Ok(text
        .lines()
        .filter(|line| line.contains("\"guide_marked\""))
        .count() as u32)
}
