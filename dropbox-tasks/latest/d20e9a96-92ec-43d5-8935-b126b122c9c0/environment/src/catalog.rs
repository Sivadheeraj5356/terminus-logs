use crate::args::Args;
use std::path::Path;

pub fn list_names(cfg: &Args) -> Result<(), String> {
    let mut rows = Vec::new();
    for entry in std::fs::read_dir(&cfg.root).map_err(|e| format!("read {}: {e}", cfg.root.display()))? {
        let entry = entry.map_err(|e| format!("dir entry: {e}"))?;
        if !entry.file_type().map_err(|e| format!("file type: {e}"))?.is_dir() {
            continue;
        }
        let repo = entry.file_name().to_string_lossy().to_string();
        let dir = entry.path().join("recipes");
        let count = count_recipes(&dir)?;
        rows.push(format!("{repo}:{count}"));
    }
    rows.sort();
    println!("{}", rows.join("\n"));
    Ok(())
}

fn count_recipes(path: &Path) -> Result<usize, String> {
    let mut n = 0usize;
    for entry in std::fs::read_dir(path).map_err(|e| format!("read {}: {e}", path.display()))? {
        let entry = entry.map_err(|e| format!("dir entry: {e}"))?;
        if entry.path().extension().and_then(|s| s.to_str()) == Some("rec") {
            n += 1;
        }
    }
    Ok(n)
}
