use std::fs;
use std::path::Path;

pub fn write_record(path: &Path, body: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, body).map_err(|e| e.to_string())
}
