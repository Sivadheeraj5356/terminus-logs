use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoeffEntry {
    pub trace_id: String,
    pub original_length: usize,
    pub effective_levels: u32,
    pub approx: Vec<f64>,
    pub details: Vec<Vec<f64>>,
    pub pad_lengths: Vec<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoeffLedger {
    pub schema_version: u32,
    pub policy_revision_id: i64,
    pub effective_levels: u32,
    pub entries: Vec<CoeffEntry>,
}

/// Authoritative sealed coefficient pack between decompose and export.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoeffPack {
    pub schema_version: u32,
    pub snapshot_digest: String,
    pub policy_revision_id: i64,
    pub mad_multiplier: f64,
    pub effective_levels: u32,
    pub pack_seal: String,
    pub entries: Vec<CoeffEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThresholdJournal {
    pub schema_version: u32,
    pub policy_revision_id: i64,
    pub mad_multiplier: f64,
    pub mad_sigma: f64,
    pub lambda0: f64,
    pub lambdas: Vec<f64>,
    pub detail_coeff_count: usize,
    pub thresholded_zero_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DenoisedTraces {
    pub schema_version: u32,
    pub policy_revision_id: i64,
    pub effective_levels: u32,
    pub traces: Vec<serde_json::Value>,
    pub content_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceAudit {
    pub trace_id: String,
    pub signal_energy: f64,
    pub residual_energy: f64,
    pub relative_residual: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoiseAudit {
    pub schema_version: u32,
    pub policy_revision_id: i64,
    pub mad_sigma: f64,
    pub total_signal_energy: f64,
    pub total_residual_energy: f64,
    pub mean_relative_residual: f64,
    pub trace_audits: Vec<TraceAudit>,
    pub content_sha256: String,
}

pub fn round12(x: f64) -> f64 {
    (x * 1e12).round() / 1e12
}

pub fn round_vec12(v: &[f64]) -> Vec<f64> {
    v.iter().copied().map(round12).collect()
}

pub fn write_pretty<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let body = serde_json::to_string_pretty(value).map_err(|e| e.to_string())?;
    let mut out = body;
    if !out.ends_with('\n') {
        out.push('\n');
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(path, out).map_err(|e| e.to_string())
}

pub fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T, String> {
    let raw = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}
