//! Seal digest ring (SHA-256 canonical payload) — BR-008 / BR-013.
//! Combinatorial Blueprint: prior_fold ouroboros binds seal digest to prior seal material;
//! Axiomatic Blindspot: plan clears prior while seal persists digest; Silent Failure: hashing
//! without prior_fold or skipping plan clear breaks multi-seal / replan digests.

use super::app_root;

pub const BR_SEAL: u32 = 8;

pub fn prior_seal_path() -> String {
    app_root::join_str("var/prior_seal.hex")
}

#[derive(Debug, Clone)]
pub struct SealParts {
    pub seq_id: String,
    pub run_epoch: u32,
    pub pages_resident: u32,
    pub mask_bits: u32,
}

impl SealParts {
    pub fn skeleton(seq_id: &str) -> Self {
        Self {
            seq_id: seq_id.to_string(),
            run_epoch: 0,
            pages_resident: 0,
            mask_bits: 0,
        }
    }
}

pub fn prior_fold_hex(prior_material: &str) -> String {
    let _ = prior_material;
    unimplemented!("blake3_seal_ring::prior_fold_hex")
}

pub fn load_prior_material() -> String {
    let _ = prior_seal_path();
    unimplemented!("blake3_seal_ring::load_prior_material")
}

pub fn clear_prior_seal() {
    let _ = prior_seal_path();
    unimplemented!("blake3_seal_ring::clear_prior_seal")
}

pub fn persist_prior_seal(digest: &str) -> std::io::Result<()> {
    let _ = (digest, prior_seal_path());
    unimplemented!("blake3_seal_ring::persist_prior_seal")
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
    let _ = SealParts::skeleton(seq_id);
    let _ = (
        run_epoch,
        pages_resident,
        phys,
        mask_bits,
        m,
        ell,
        prior_fold,
        compact_gen,
        visit_checksum,
        merkle_tip,
        compiler_epoch,
        rebuild_nonce,
        schedule_crc,
        residue_u64,
    );
    unimplemented!("blake3_seal_ring::payload")
}

pub fn digest_hex(payload: &str) -> String {
    let _ = payload;
    unimplemented!("blake3_seal_ring::digest_hex")
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
