//! Coefficient-pack seal helpers.

use crate::ingest::TraceSnapshot;
use crate::staging::{self, CoeffEntry, CoeffPack};
use sha2::{Digest, Sha256};

pub fn snapshot_digest(snap: &TraceSnapshot) -> Result<String, String> {
    let payload = serde_json::json!({
        "case_id": snap.case_id,
        "mad_multiplier": snap.mad_multiplier,
        "max_levels": snap.max_levels,
        "policy_revision_id": snap.policy_revision_id,
        "requested_levels": snap.requested_levels,
        "schema_version": snap.schema_version,
        "traces": snap.traces,
    });
    let bytes = serde_json::to_vec(&payload).map_err(|e| e.to_string())?;
    Ok(hex_encode(Sha256::digest(&bytes).as_slice()))
}

/// Starter seal: hashes only the first approximation vector (unbound).
pub fn compute_pack_seal(
    _snapshot_digest: &str,
    _policy_revision_id: i64,
    entries: &[CoeffEntry],
) -> String {
    let mut hasher = Sha256::new();
    if let Some(first) = entries.first() {
        for v in &first.approx {
            hasher.update(format!("{v:.12}").as_bytes());
            hasher.update(b",");
        }
    }
    hex_encode(hasher.finalize().as_slice())
}

pub fn build_pack(
    snap: &TraceSnapshot,
    entries: Vec<CoeffEntry>,
    effective_levels: u32,
) -> Result<CoeffPack, String> {
    let digest = snapshot_digest(snap)?;
    let seal = compute_pack_seal(&digest, snap.policy_revision_id, &entries);
    Ok(CoeffPack {
        schema_version: 2,
        snapshot_digest: digest,
        policy_revision_id: snap.policy_revision_id,
        mad_multiplier: staging::round12(snap.mad_multiplier),
        effective_levels,
        pack_seal: seal,
        entries,
    })
}

/// Starter verifier: accepts any non-empty seal string.
pub fn verify_pack(pack: &CoeffPack, _snap: &TraceSnapshot) -> Result<(), String> {
    if pack.pack_seal.is_empty() {
        return Err("missing pack_seal".into());
    }
    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
