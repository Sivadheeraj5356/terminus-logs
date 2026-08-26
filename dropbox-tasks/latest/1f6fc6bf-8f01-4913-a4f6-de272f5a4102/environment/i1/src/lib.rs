use serde::Deserialize;
use thiserror::Error;

#[derive(Debug, Clone, Deserialize)]
pub struct Workload {
    pub schema_version: u32,
    pub workload_id: String,
    pub rounds: Vec<RoundSpec>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RoundSpec {
    pub round_index: u32,
    pub shard: u32,
    pub op: String,
}

#[derive(Debug, Error)]
pub enum WorkloadError {
    #[error("read workload: {0}")]
    Read(#[from] std::io::Error),
    #[error("parse workload: {0}")]
    Parse(#[from] serde_json::Error),
    #[error("unsupported schema_version {0}")]
    Schema(u32),
    #[error("empty workload")]
    Empty,
    #[error("duplicate round_index {0}")]
    DuplicateRound(u32),
}

pub fn load(path: &str) -> Result<Workload, WorkloadError> {
    let raw = std::fs::read_to_string(path)?;
    let wl: Workload = serde_json::from_str(&raw)?;
    if wl.schema_version != 1 {
        return Err(WorkloadError::Schema(wl.schema_version));
    }
    if wl.rounds.is_empty() {
        return Err(WorkloadError::Empty);
    }
    let mut seen = std::collections::HashSet::new();
    for r in &wl.rounds {
        if !seen.insert(r.round_index) {
            return Err(WorkloadError::DuplicateRound(r.round_index));
        }
    }
    Ok(wl)
}
