use std::fs;
use std::path::Path;

pub fn next_ingest_seq() -> Result<u64, String> {
    let path = Path::new("/app/state/ingest_seq.txt");
    let cur = if path.is_file() {
        fs::read_to_string(path)
            .map_err(|e| e.to_string())?
            .trim()
            .parse::<u64>()
            .unwrap_or(0)
    } else {
        0
    };
    let next = cur + 1;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, format!("{next}\n")).map_err(|e| e.to_string())?;
    Ok(next)
}
