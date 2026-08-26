use std::fs;
use std::path::Path;

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Slot {
    pub resource: String,
    pub start_ms: u64,
    pub end_ms: u64,
    pub holder: String,
    pub slot_id: u64,
    #[serde(default)]
    pub epoch: u64,
    #[serde(skip)]
    pub source_file: String,
}

/// Resource ids are grouped case-insensitively.
pub fn canonical_resource(resource: &str) -> String {
    resource.trim().to_ascii_lowercase()
}

pub fn read_file(path: &Path) -> Result<Vec<Slot>, String> {
    let source_file = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    let text = fs::read_to_string(path).map_err(|e| format!("cannot read {}: {}", path.display(), e))?;
    let mut out = Vec::new();
    for (lineno, line) in text.lines().enumerate() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let mut row: Slot = serde_json::from_str(trimmed)
            .map_err(|e| format!("invalid json at line {}: {}", lineno + 1, e))?;
        row.source_file = source_file.clone();
        out.push(row);
    }
    Ok(out)
}

pub fn list_slot_files(dir: &str) -> Result<Vec<String>, String> {
    let mut paths = Vec::new();
    for entry in fs::read_dir(dir).map_err(|e| format!("cannot open {}: {}", dir, e))? {
        let entry = entry.map_err(|e| format!("read dir entry: {}", e))?;
        let name = entry.file_name().to_string_lossy().to_string();
        if name.ends_with(".slot") {
            paths.push(entry.path().to_string_lossy().to_string());
        }
    }
    paths.sort();
    Ok(paths)
}

pub fn load_all(dir: &str) -> Result<Vec<Slot>, String> {
    let paths = list_slot_files(dir)?;
    if paths.is_empty() {
        return Err("no slots".to_string());
    }
    let mut out = Vec::new();
    for path in &paths {
        out.extend(read_file(Path::new(path))?);
    }
    Ok(out)
}
