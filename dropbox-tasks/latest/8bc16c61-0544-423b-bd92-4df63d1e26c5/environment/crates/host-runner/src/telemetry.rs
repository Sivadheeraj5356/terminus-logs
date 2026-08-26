use std::fs;
use std::path::{Path, PathBuf};

pub fn fixture_paths(root: &Path) -> Result<Vec<PathBuf>, String> {
    let mut paths = fs::read_dir(root)
        .map_err(|err| format!("read fixture dir: {err}"))?
        .map(|entry| entry.map(|entry| entry.path()))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("read fixture entry: {err}"))?;
    paths.retain(|path| path.extension().and_then(|ext| ext.to_str()) == Some("bin"));
    paths.sort();
    if paths.is_empty() {
        return Err("no telemetry fixtures found".to_string());
    }
    Ok(paths)
}

pub fn read_fixture(path: &Path) -> Result<Vec<u8>, String> {
    fs::read(path).map_err(|err| format!("read fixture {}: {err}", path.display()))
}
