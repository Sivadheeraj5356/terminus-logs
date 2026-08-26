//! Coefficient-pack seal helpers (authoritative binding).

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

pub fn compute_pack_seal(
    snapshot_digest: &str,
    policy_revision_id: i64,
    entries: &[CoeffEntry],
) -> String {
    let mut hasher = Sha256::new();
    hasher.update(snapshot_digest.as_bytes());
    hasher.update(b"|");
    hasher.update(policy_revision_id.to_string().as_bytes());
    hasher.update(b"|");
    for entry in entries {
        hasher.update(entry.trace_id.as_bytes());
        hasher.update(b"|");
        hasher.update(entry.original_length.to_string().as_bytes());
        hasher.update(b"|");
        hasher.update(entry.effective_levels.to_string().as_bytes());
        hasher.update(b"|");
        for p in &entry.pad_lengths {
            hasher.update(p.to_string().as_bytes());
            hasher.update(b",");
        }
        hasher.update(b"|");
        for v in &entry.approx {
            hasher.update(format!("{v:.12}").as_bytes());
            hasher.update(b",");
        }
        hasher.update(b"|");
        for band in &entry.details {
            for v in band {
                hasher.update(format!("{v:.12}").as_bytes());
                hasher.update(b",");
            }
            hasher.update(b";");
        }
        hasher.update(b"#");
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

pub fn verify_pack(pack: &CoeffPack, snap: &TraceSnapshot) -> Result<(), String> {
    if pack.schema_version != 2 {
        return Err(format!(
            "coeff-pack schema_version must be 2, got {}",
            pack.schema_version
        ));
    }
    let expected_digest = snapshot_digest(snap)?;
    if pack.snapshot_digest != expected_digest {
        return Err("coeff-pack snapshot_digest does not match live snapshot".into());
    }
    if pack.policy_revision_id != snap.policy_revision_id {
        return Err("coeff-pack policy_revision_id does not match snapshot".into());
    }
    if (pack.mad_multiplier - snap.mad_multiplier).abs() > 1e-15 {
        return Err("coeff-pack mad_multiplier does not match snapshot".into());
    }
    let expected_seal =
        compute_pack_seal(&pack.snapshot_digest, pack.policy_revision_id, &pack.entries);
    if pack.pack_seal != expected_seal {
        return Err("coeff-pack pack_seal mismatch".into());
    }
    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
