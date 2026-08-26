use std::fs;

/// Inventory helper: alphabetical graph basenames under the vault.
pub fn scan_m() -> Result<Vec<String>, String> {
    let mut names = Vec::new();
    for entry in fs::read_dir("/app/environment/vault/graphs").map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.ends_with(".json") {
            names.push(name);
        }
    }
    names.sort();
    Ok(names)
}
