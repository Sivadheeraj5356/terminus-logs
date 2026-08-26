use std::fs;
use std::path::Path;

use crate::k3::lane::{Lane, ReloadSeed};
use crate::k3::report::SendReport;

pub fn load_lanes(dir: &Path) -> Result<Vec<Lane>, String> {
    let mut lanes = Vec::new();
    let mut paths: Vec<_> = fs::read_dir(dir)
        .map_err(|e| e.to_string())?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    paths.sort();
    for path in paths {
        let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let lane: Lane = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        lanes.push(lane);
    }
    Ok(lanes)
}

pub fn load_reload_seeds(dir: &Path) -> Result<Vec<ReloadSeed>, String> {
    if !dir.is_dir() {
        return Ok(Vec::new());
    }
    let mut seeds = Vec::new();
    let mut paths: Vec<_> = fs::read_dir(dir)
        .map_err(|e| e.to_string())?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    paths.sort();
    for path in paths {
        let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let seed: ReloadSeed = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        seeds.push(seed);
    }
    Ok(seeds)
}

pub fn write_report(path: &Path, report: &SendReport) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(report).map_err(|e| e.to_string())?;
    fs::write(path, format!("{text}\n")).map_err(|e| e.to_string())
}

pub fn write_stream(path: &Path, bytes: &[u8]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, bytes).map_err(|e| e.to_string())
}
