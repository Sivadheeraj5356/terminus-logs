pub mod decompose_stage;
pub mod export_stage;
pub mod fft_denoise;
pub mod haar;
pub mod ingest;
pub mod seal;
pub mod staging;
pub mod threshold;

use std::env;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct Paths {
    pub data: PathBuf,
    pub state: PathBuf,
    pub output: PathBuf,
}

pub fn resolve_paths() -> Result<Paths, String> {
    Ok(Paths {
        data: abs_override("HAAR_DATA_DIR", "/app/data")?,
        state: abs_override("HAAR_STATE_DIR", "/app/state")?,
        output: abs_override("HAAR_OUTPUT_DIR", "/app/output")?,
    })
}

fn abs_override(key: &str, default: &str) -> Result<PathBuf, String> {
    match env::var(key) {
        Ok(v) => {
            let p = PathBuf::from(&v);
            if !p.is_absolute() {
                return Err(format!("{key} must be an absolute path"));
            }
            Ok(p)
        }
        Err(_) => Ok(PathBuf::from(default)),
    }
}

pub fn ensure_dir(p: &Path) -> Result<(), String> {
    std::fs::create_dir_all(p).map_err(|e| e.to_string())
}

pub fn run_ingest(paths: &Paths) -> Result<(), String> {
    ingest::ingest_traces(paths)
}

pub fn run_decompose(paths: &Paths) -> Result<(), String> {
    decompose_stage::decompose_threshold(paths)
}

pub fn run_export(paths: &Paths) -> Result<(), String> {
    export_stage::reconstruct_export(paths)
}

pub fn run_all(paths: &Paths) -> Result<(), String> {
    run_ingest(paths)?;
    run_decompose(paths)?;
    run_export(paths)?;
    Ok(())
}
