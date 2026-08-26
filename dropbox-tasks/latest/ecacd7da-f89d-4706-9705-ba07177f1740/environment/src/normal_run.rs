use crate::ledger::SeatLedger;
use crate::replay::ReplayContext;
use crate::report::build_report;
use std::fs;
use std::path::PathBuf;

pub fn run(events_path: &str, log_path: &str, report_path: Option<&str>) -> Result<(), String> {
    if PathBuf::from(log_path).exists() {
        fs::remove_file(log_path).ok();
    }
    let mut ctx = ReplayContext::new(SeatLedger::new());
    ctx.log_path = Some(log_path.to_string());
    ctx.replay_file(events_path, "/app/data/rams")?;
    if let Some(path) = report_path {
        let body = build_report(&ctx.ledger, false, count_guide_mark(log_path)?);
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
