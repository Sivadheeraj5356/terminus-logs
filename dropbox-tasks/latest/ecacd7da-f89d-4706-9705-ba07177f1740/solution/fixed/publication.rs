use std::fs;
use std::path::{Path, PathBuf};

#[derive(Default)]
pub struct PriorArtifacts {
    pub log: Option<Vec<u8>>,
    pub report: Option<Vec<u8>>,
}

pub fn publish_normal_run(
    events_path: &str,
    log_path: &str,
    report_path: Option<&str>,
) -> Result<(), String> {
    crate::staged_run::run(events_path, log_path, report_path)
}

pub fn capture_prior(log_path: &Path, report_path: Option<&Path>) -> Result<PriorArtifacts, String> {
    let log = log_path
        .exists()
        .then(|| fs::read(log_path).map_err(|e| e.to_string()))
        .transpose()?;
    let report = report_path
        .and_then(|path| path.exists().then(|| fs::read(path).map_err(|e| e.to_string())))
        .transpose()?;
    Ok(PriorArtifacts { log, report })
}

pub fn restore_prior(
    log_path: &Path,
    report_path: Option<&Path>,
    prior: &PriorArtifacts,
) -> Result<(), String> {
    restore_one(log_path, prior.log.as_deref())?;
    if let Some(path) = report_path {
        restore_one(path, prior.report.as_deref())?;
    }
    Ok(())
}

fn restore_one(path: &Path, prior: Option<&[u8]>) -> Result<(), String> {
    match prior {
        Some(bytes) => fs::write(path, bytes).map_err(|e| e.to_string()),
        None => {
            if path.exists() {
                fs::remove_file(path).map_err(|e| e.to_string())?;
            }
            Ok(())
        }
    }
}

pub fn stage_path(target: &Path) -> PathBuf {
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    parent.join(format!(
        ".{}.stage",
        target.file_name().unwrap_or_default().to_string_lossy()
    ))
}

pub fn temp_path(target: &Path, suffix: u8) -> PathBuf {
    PathBuf::from(format!("{}.tmp.{suffix}", target.to_string_lossy()))
}

pub fn cleanup_artifacts(paths: &[PathBuf]) {
    for path in paths {
        if path.exists() {
            let _ = fs::remove_file(path);
        }
    }
}

pub fn cleanup_temp_siblings(target: &Path) {
    for suffix in 0u8..=2 {
        let candidate = temp_path(target, suffix);
        if candidate.exists() {
            let _ = fs::remove_file(candidate);
        }
    }
    let stage = stage_path(target);
    if stage.exists() {
        let _ = fs::remove_file(stage);
    }
}

pub fn publish_staged(stage: &Path, target: &Path) -> Result<(), String> {
    let tmp = pick_temp_path(target)?;
    fs::copy(stage, &tmp).map_err(|e| e.to_string())?;
    if target.exists() {
        fs::remove_file(target).map_err(|e| e.to_string())?;
    }
    fs::rename(&tmp, target).map_err(|e| e.to_string())?;
    if stage.exists() {
        let _ = fs::remove_file(stage);
    }
    Ok(())
}

fn pick_temp_path(dest: &Path) -> Result<PathBuf, String> {
    for suffix in 0u8..=2 {
        let candidate = temp_path(dest, suffix);
        if !candidate.exists() {
            return Ok(candidate);
        }
    }
    Err(format!(
        "unable to allocate temp path for {}",
        dest.display()
    ))
}
