use crate::model::AssayBundle;
use sha2::{Digest, Sha256};
use serde_json::Value;

pub fn config_canon_sha(bundle: &AssayBundle) -> String {
    let mut ids: Vec<&str> = bundle.coins.iter().map(|c| c.coin_id.as_str()).collect();
    ids.sort();
    let material = ids.join("|");
    hex_sha256(material.as_bytes())
}

pub fn compute_bind(config_canon_sha: &str, ingest_seq: u64) -> String {
    let material = format!("{config_canon_sha}:{ingest_seq}");
    hex_sha256(material.as_bytes())
}

pub fn verify_snapshot_bind(snap: &Value, bundle: &AssayBundle) -> Result<(), String> {
    let got = snap
        .get("assay_bind")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing assay_bind".to_string())?;
    if got != bundle.assay_bind {
        return Err("assay_bind mismatch".to_string());
    }
    Ok(())
}

fn hex_sha256(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}
