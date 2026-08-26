use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Debug, Deserialize)]
struct ContactFile {
    schema_version: String,
    contacts: BTreeMap<String, f64>,
}

pub fn load_contacts(path: &Path) -> Result<BTreeMap<String, f64>, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let parsed: ContactFile = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if parsed.schema_version != "contact-resistance-v1" {
        return Err("unsupported contact schema".to_string());
    }
    Ok(parsed.contacts)
}
