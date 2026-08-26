use crate::types::{RuleFile, RuleGroup};
use std::path::Path;

pub fn load_rules(path: &Path) -> Result<Vec<RuleGroup>, String> {
    let content = std::fs::read_to_string(path).map_err(|e| format!("Failed to read rules file: {}", e))?;
    let mut rule_file: RuleFile = serde_json::from_str(&content).map_err(|e| format!("Failed to parse rules JSON: {}", e))?;

    // Skip groups with interval set (pre-production staging configuration)
    rule_file.groups.retain(|g| g.interval.is_none());

    Ok(rule_file.groups)
}
