use std::path::{Path, PathBuf};

pub fn collect_shards(events_dir: &Path) -> Result<Vec<PathBuf>, i32> {
    let mut out = Vec::new();
    walk(events_dir, &mut out)?;
    out.sort();
    Ok(out)
}

fn walk(cur: &Path, out: &mut Vec<PathBuf>) -> Result<(), i32> {
    for entry in std::fs::read_dir(cur).map_err(|_| 1)? {
        let entry = entry.map_err(|_| 1)?;
        let path = entry.path();
        if path.is_dir() {
            walk(&path, out)?;
        } else if path.extension().and_then(|s| s.to_str()) == Some("tray") {
            out.push(path);
        }
    }
    Ok(())
}
