use super::app_root;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

pub fn prior_seal_path() -> String {
    app_root::join_str("var/prior_seal.hex")
}

pub fn prior_fold_hex(prior_material: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(prior_material.as_bytes());
    hex::encode(hasher.finalize())[..16].to_string()
}

pub fn load_prior_material() -> String {
    let p = prior_seal_path();
    if let Ok(s) = fs::read_to_string(&p) {
        let t = s.trim().to_string();
        if t.len() == 64 && t.chars().all(|c| c.is_ascii_hexdigit()) {
            return t.to_ascii_lowercase();
        }
    }
    "0".repeat(64)
}

pub fn clear_prior_seal() {
    let _ = fs::remove_file(prior_seal_path());
}

pub fn persist_prior_seal(digest: &str) -> std::io::Result<()> {
    let path = prior_seal_path();
    if let Some(parent) = Path::new(&path).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, digest)
}

pub fn compiler_epoch_path() -> String {
    app_root::join_str("var/compiler-epoch.json")
}

pub fn load_compiler_epoch() -> u64 {
    let p = compiler_epoch_path();
    if let Ok(raw) = fs::read_to_string(&p) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(raw.trim()) {
            if let Some(n) = v.get("epoch_u64").and_then(|x| x.as_u64()) {
                return n;
            }
        }
    }
    0
}

pub fn load_rebuild_nonce() -> u64 {
    let p = compiler_epoch_path();
    if let Ok(raw) = fs::read_to_string(&p) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(raw.trim()) {
            if let Some(n) = v.get("rebuild_nonce").and_then(|x| x.as_u64()) {
                return n;
            }
        }
    }
    0
}

pub fn payload(
    seq_id: &str,
    run_epoch: u32,
    pages_resident: u32,
    phys: &[u32],
    mask_bits: u32,
    m: &[String],
    ell: &[String],
    prior_fold: &str,
    compact_gen: u32,
    visit_checksum: u32,
    merkle_tip: u64,
    compiler_epoch: u64,
    rebuild_nonce: u64,
    schedule_crc: u32,
    residue_u64: u64,
) -> String {
    // Caller must pass physical ids already ordered by ascending logical key.
    let pages = phys
        .iter()
        .map(|p| p.to_string())
        .collect::<Vec<_>>()
        .join(",");
    format!(
        "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}",
        seq_id,
        run_epoch,
        pages_resident,
        pages,
        mask_bits,
        m.join(","),
        ell.join(","),
        prior_fold,
        compact_gen,
        visit_checksum,
        merkle_tip,
        compiler_epoch,
        rebuild_nonce,
        schedule_crc,
        residue_u64
    )
}

pub fn digest_hex(payload: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    hex::encode(hasher.finalize())
}

pub fn key_order() -> &'static [&'static str] {
    &[
        "seq_id",
        "run_epoch",
        "tiles_planned",
        "pages_resident",
        "mask_bits",
        "m_stats",
        "ell_stats",
        "seal_digest",
    ]
}
