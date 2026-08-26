use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::hash::bind_crc;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Report {
    pub report_id: String,
    pub dive_lane: String,
    pub confidence_rank: u32,
    pub revision: u32,
    #[serde(default)]
    pub supersedes: Option<String>,
    pub calibration_valid: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Observation {
    pub obs_id: String,
    pub dive_lane: String,
    pub timestamp_utc: String,
    pub obs_type: String,
    pub depth_m: i32,
    pub feature_code: String,
    pub instrument_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StagingArtifact {
    pub expedition_id: String,
    pub report_count: u32,
    pub observation_count: u32,
    pub reports: Vec<Report>,
    pub observations: Vec<Observation>,
    pub staging_bind: String,
}

pub fn load_bundle(path: &Path) -> Result<StagingArtifact, String> {
    let mut raw = std::fs::read_to_string(path).map_err(|_| "DIVE_READ_ERROR".to_string())?;
    if let Some(stripped) = raw.strip_prefix('\u{feff}') {
        raw = stripped.to_string();
    }
    let bundle: serde_json::Value =
        serde_json::from_str(&raw).map_err(|_| "DIVE_FORMAT_ERROR".to_string())?;
    let expedition_id = bundle
        .get("expedition_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "DIVE_FORMAT_ERROR".to_string())?
        .to_string();
    let reports: Vec<Report> =
        serde_json::from_value(bundle.get("reports").cloned().unwrap_or_default())
            .map_err(|_| "DIVE_FORMAT_ERROR".to_string())?;
    let observations: Vec<Observation> =
        serde_json::from_value(bundle.get("observations").cloned().unwrap_or_default())
            .map_err(|_| "DIVE_FORMAT_ERROR".to_string())?;
    if reports.is_empty() || observations.is_empty() {
        return Err("DIVE_FORMAT_ERROR".to_string());
    }
    let report_ids: Vec<String> = reports.iter().map(|r| r.report_id.clone()).collect();
    let staging_bind = bind_crc::staging_bind(&expedition_id, &report_ids);
    Ok(StagingArtifact {
        expedition_id,
        report_count: reports.len() as u32,
        observation_count: observations.len() as u32,
        reports,
        observations,
        staging_bind,
    })
}

pub fn write_staging(path: &Path, artifact: &StagingArtifact) -> Result<(), i32> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::to_string_pretty(artifact).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

pub fn load_staging(path: &Path) -> Result<StagingArtifact, String> {
    let raw = std::fs::read_to_string(path).map_err(|_| "STAGING_PARSE_ERROR".to_string())?;
    serde_json::from_str(&raw).map_err(|_| "STAGING_PARSE_ERROR".to_string())
}
