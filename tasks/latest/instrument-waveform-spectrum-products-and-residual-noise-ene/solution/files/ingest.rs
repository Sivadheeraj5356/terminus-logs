use crate::Paths;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DenoiseConfig {
    pub schema_version: u32,
    pub case_id: String,
    pub requested_levels: u32,
    pub max_levels: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThresholdPolicy {
    pub revision_id: i64,
    pub effective_at: String,
    pub case_id: String,
    pub mad_multiplier: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceFile {
    pub trace_id: String,
    pub sample_rate_hz: f64,
    pub samples: Vec<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceSnapEntry {
    pub trace_id: String,
    pub sample_rate_hz: f64,
    pub samples: Vec<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceSnapshot {
    pub schema_version: u32,
    pub case_id: String,
    pub policy_revision_id: i64,
    pub mad_multiplier: f64,
    pub requested_levels: u32,
    pub max_levels: u32,
    pub traces: Vec<TraceSnapEntry>,
}

pub fn ingest_traces(paths: &Paths) -> Result<(), String> {
    crate::ensure_dir(&paths.state)?;
    let cfg = load_config(&paths.data.join("denoise-config.json"))?;
    let policy = select_policy(&paths.data.join("threshold-policies"), &cfg.case_id)?;
    let mut traces = load_traces(&paths.data.join("traces"))?;
    traces.sort_by(|a, b| a.trace_id.cmp(&b.trace_id));
    let snap = TraceSnapshot {
        schema_version: 1,
        case_id: cfg.case_id,
        policy_revision_id: policy.revision_id,
        mad_multiplier: crate::staging::round12(policy.mad_multiplier),
        requested_levels: cfg.requested_levels,
        max_levels: cfg.max_levels,
        traces: traces
            .into_iter()
            .map(|t| TraceSnapEntry {
                trace_id: t.trace_id,
                sample_rate_hz: crate::staging::round12(t.sample_rate_hz),
                samples: crate::staging::round_vec12(&t.samples),
            })
            .collect(),
    };
    crate::staging::write_pretty(&paths.state.join("trace-snapshot.json"), &snap)
}

fn load_config(path: &Path) -> Result<DenoiseConfig, String> {
    let raw = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&raw).map_err(|e| e.to_string())
}

fn load_traces(dir: &Path) -> Result<Vec<TraceFile>, String> {
    let mut out = Vec::new();
    let mut entries: Vec<_> = fs::read_dir(dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let path = e.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let raw = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let t: TraceFile = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        out.push(t);
    }
    if out.is_empty() {
        return Err("no traces found".into());
    }
    Ok(out)
}

pub fn select_policy(dir: &Path, case_id: &str) -> Result<ThresholdPolicy, String> {
    let mut matched = Vec::new();
    let mut entries: Vec<_> = fs::read_dir(dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let path = e.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let raw = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let p: ThresholdPolicy = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        if p.case_id == case_id {
            matched.push(p);
        }
    }
    if matched.is_empty() {
        return Err(format!("no threshold policy for case_id={case_id}"));
    }
    matched.sort_by(|a, b| match b.effective_at.cmp(&a.effective_at) {
        std::cmp::Ordering::Equal => b.revision_id.cmp(&a.revision_id),
        other => other,
    });
    Ok(matched[0].clone())
}
