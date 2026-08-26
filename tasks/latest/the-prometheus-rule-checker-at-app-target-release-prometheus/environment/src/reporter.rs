use crate::types::Report;
use std::path::Path;

pub fn write_report(report: &Report, path: &Path) -> Result<(), String> {
    let json = serde_json::to_string_pretty(report).map_err(|e| format!("Failed to serialize report: {}", e))?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create output directory: {}", e))?;
    }
    std::fs::write(path, json).map_err(|e| format!("Failed to write report: {}", e))?;
    Ok(())
}
