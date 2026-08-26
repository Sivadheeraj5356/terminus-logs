use crate::atlas;
use crate::atlas::bundle_from_snapshot;
use crate::binding;
use crate::export_stage;
use crate::ingest;
use crate::ledger;
use crate::seq;
use serde_json::Value;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

pub enum PipelineError {
    MissingSnapshot,
    Io(String),
}

const SNAPSHOT: &str = "/app/state/assay-snapshot.json";

fn abs_override(var: &str, default: &str) -> Result<PathBuf, PipelineError> {
    match env::var(var) {
        Ok(p) if !p.is_empty() => {
            let path = PathBuf::from(&p);
            if !path.is_absolute() {
                return Err(PipelineError::Io(format!("{var} must be absolute")));
            }
            Ok(path)
        }
        _ => Ok(PathBuf::from(default)),
    }
}

pub fn run_analyze_publish() -> Result<(), PipelineError> {
    let cfg_path = abs_override("TB3_ASSAY_CONFIG", "/app/data/assay-config.json")?;
    let coins_path = abs_override("TB3_COINS", "/app/data/coins.json")?;
    let metals_path = abs_override("TB3_METAL_DENSITIES", "/app/data/metal-densities.json")?;
    let models_path = abs_override("TB3_ENRICHMENT_MODELS", "/app/data/enrichment-models.json")?;

    let mut bundle = ingest::build_bundle(&cfg_path, &coins_path, &metals_path, &models_path)
        .map_err(PipelineError::Io)?;
    bundle.ingest_seq = seq::next_ingest_seq().map_err(PipelineError::Io)?;
    bundle.config_canon_sha = binding::config_canon_sha(&bundle);
    bundle.assay_bind = binding::compute_bind(&bundle.config_canon_sha, bundle.ingest_seq);
    atlas::write_snapshot(Path::new(SNAPSHOT), &bundle).map_err(PipelineError::Io)?;
    ledger::record(bundle.ingest_seq, &bundle.assay_bind).map_err(PipelineError::Io)?;
    export_stage::publish_from_bundle(&bundle).map_err(PipelineError::Io)?;
    Ok(())
}

pub fn run_check_coin(coin_id: &str) -> Result<(), PipelineError> {
    run_analyze_publish()?;
    let raw = fs::read(SNAPSHOT).map_err(|e| PipelineError::Io(e.to_string()))?;
    let snap: Value =
        serde_json::from_slice(&raw).map_err(|e| PipelineError::Io(e.to_string()))?;
    let coins = snap
        .get("coins")
        .and_then(|c| c.as_array())
        .ok_or_else(|| PipelineError::Io("bad snapshot".into()))?;
    for c in coins {
        if c.get("coin_id").and_then(|v| v.as_str()) == Some(coin_id) {
            println!("{}", serde_json::to_string_pretty(c).unwrap_or_default());
            return Ok(());
        }
    }
    Err(PipelineError::Io(format!("unknown coin_id {coin_id}")))
}

pub fn run_export() -> Result<(), PipelineError> {
    if !Path::new(SNAPSHOT).is_file() {
        return Err(PipelineError::MissingSnapshot);
    }
    let raw = fs::read(SNAPSHOT).map_err(|e| PipelineError::Io(e.to_string()))?;
    let snap: Value =
        serde_json::from_slice(&raw).map_err(|e| PipelineError::Io(e.to_string()))?;
    let bundle = bundle_from_snapshot(&snap).map_err(PipelineError::Io)?;
    binding::verify_snapshot_bind(&snap, &bundle).map_err(PipelineError::Io)?;
    ledger::verify_matches_snapshot(bundle.ingest_seq, &bundle.assay_bind)
        .map_err(PipelineError::Io)?;
    export_stage::publish_from_bundle(&bundle).map_err(PipelineError::Io)?;
    Ok(())
}
