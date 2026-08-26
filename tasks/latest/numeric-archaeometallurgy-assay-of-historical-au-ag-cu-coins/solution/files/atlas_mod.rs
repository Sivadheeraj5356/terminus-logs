use crate::model::AssayBundle;
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

pub fn write_snapshot(path: &Path, bundle: &AssayBundle) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let raw = serde_json::to_vec_pretty(bundle).map_err(|e| e.to_string())?;
    fs::write(path, raw).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn bundle_from_snapshot(snap: &Value) -> Result<AssayBundle, String> {
    serde_json::from_value(snap.clone()).map_err(|e| e.to_string())
}

pub fn publish_outputs(
    results_path: &Path,
    trace_path: &Path,
    inconsistent_path: &Path,
    audit_path: &Path,
    bundle: &AssayBundle,
) -> Result<(), String> {
    let mut coins_out = Vec::new();
    let mut trace_coins = Vec::new();
    let mut inconsistent = Vec::new();
    let mut feasible = 0usize;
    let mut dens_only = 0usize;
    let mut insuff = 0usize;

    for c in &bundle.coins {
        match c.status.as_str() {
            "feasible" => feasible += 1,
            "inconsistent" => inconsistent.push(c.coin_id.clone()),
            "density_only" => dens_only += 1,
            "insufficient_data" => insuff += 1,
            _ => {}
        }
        coins_out.push(json!({
            "coin_id": c.coin_id,
            "status": c.status,
            "reason": c.reason,
            "feasible_region": c.feasible_region,
        }));
        trace_coins.push(json!({
            "coin_id": c.coin_id,
            "density_band": c.density_band,
            "xrf_bound": c.xrf_bound,
            "intersection_point_count": c.intersection_point_count,
        }));
    }
    inconsistent.sort();

    let results = json!({
        "schema_version": 1,
        "coins": coins_out,
    });
    let trace = json!({
        "schema_version": 1,
        "coins": trace_coins,
    });
    let inc = json!({
        "schema_version": 1,
        "coin_ids": inconsistent,
    });
    let audit = json!({
        "schema_version": 1,
        "coin_count": bundle.coins.len(),
        "feasible_count": feasible,
        "inconsistent_count": inconsistent.len(),
        "density_only_count": dens_only,
        "insufficient_count": insuff,
        "assay_bind": bundle.assay_bind,
        "ingest_seq": bundle.ingest_seq,
    });

    write_json(results_path, &results)?;
    write_json(trace_path, &trace)?;
    write_json(inconsistent_path, &inc)?;
    write_json(audit_path, &audit)?;
    Ok(())
}

fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let raw = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
    fs::write(path, raw).map_err(|e| e.to_string())?;
    Ok(())
}
