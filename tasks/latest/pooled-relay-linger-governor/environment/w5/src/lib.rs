use prlg_k4::ReclaimRow;
use serde::Serialize;
use std::fs;
use thiserror::Error;

#[derive(Debug, Clone, Serialize)]
pub struct RunReport {
    pub schema_version: u32,
    pub workload_id: String,
    pub round_count: u32,
    pub pool_generation: u32,
    pub checkouts_total: u32,
    pub reclaims_total: u32,
    pub journal_digest: String,
    pub pool_peak: u32,
    pub state_bytes: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct TraceEvent {
    pub socket_id: u32,
    pub phase: String,
    pub pool_generation: u32,
    pub shard: u32,
}

#[derive(Debug, Error)]
pub enum ExportError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("cross surface mismatch")]
    Mismatch,
}

pub fn emit_f(
    report_path: &str,
    journal_path: &str,
    trace_path: &str,
    report: &RunReport,
    reclaims: &[ReclaimRow],
    trace: &[TraceEvent],
    require_full: bool,
) -> Result<(), ExportError> {
    if report.reclaims_total != reclaims.len() as u32 {
        return Err(ExportError::Mismatch);
    }
    if require_full && report.checkouts_total < report.round_count {
        return Err(ExportError::Mismatch);
    }

    fs::write(report_path, serde_json::to_vec_pretty(report)?)?;

    let mut csv = String::from("socket_id,shard,event,pool_generation,round_index\n");
    for row in reclaims {
        csv.push_str(&format!(
            "{},{},{},{},{}\n",
            row.socket_id, row.shard, row.event, row.pool_generation, row.round_index
        ));
    }
    fs::write(journal_path, csv)?;

    let mut ndjson = String::new();
    for ev in trace {
        ndjson.push_str(&serde_json::to_string(ev)?);
        ndjson.push('\n');
    }
    fs::write(trace_path, ndjson)?;
    Ok(())
}
