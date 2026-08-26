use std::fs;
use std::path::Path;

use o0m::{BalanceReport, ZoneBalance};

fn arrange_rows(rows: &mut Vec<ZoneBalance>) {
    rows.sort_by(|a, b| a.zone.cmp(&b.zone));
    rows.dedup_by(|a, b| a.zone == b.zone);
}

pub fn layout_zones(mut rows: Vec<ZoneBalance>) -> Vec<ZoneBalance> {
    arrange_rows(&mut rows);
    rows
}

pub fn write_report(path: &Path, report: &BalanceReport) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let body = serde_json::to_string_pretty(report).map_err(|e| e.to_string())?;
    fs::write(path, body + "\n").map_err(|e| e.to_string())
}
