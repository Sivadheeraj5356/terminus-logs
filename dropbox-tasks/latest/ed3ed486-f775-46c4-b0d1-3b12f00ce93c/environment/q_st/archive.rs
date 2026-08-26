use std::fs;
use std::path::Path;

/// Read-only archive compaction unrelated to live training.
pub fn compact_archive(root: &Path) -> Result<usize, String> {
    let mut count = 0usize;
    if !root.exists() {
        return Ok(0);
    }
    for entry in fs::read_dir(root).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if entry.file_type().map_err(|e| e.to_string())?.is_file() {
            count += 1;
        }
    }
    Ok(count)
}
