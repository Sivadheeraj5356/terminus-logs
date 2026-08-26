use anyhow::{bail, Result};
use std::fs;
use std::path::Path;
use crate::internal::{blake3_seal_ring, cascade_hook, online_softmax_ring, schedule_mirror, seal_trailer};
use crate::ledger::ResidencyLedger;
use crate::profile::AttnProfile;

pub fn run_seal(ledger: &ResidencyLedger, profile: &AttnProfile, seq_id: &str, out: &str) -> Result<()> {
    if !cascade_hook::require_nonzero_pages(ledger.pages_resident()) {
        bail!("no resident pages");
    }
    let mut pairs = ledger.map.clone();
    pairs.sort_by_key(|(l, _)| *l);
    let phys: Vec<u32> = pairs.iter().map(|(_, p)| *p).collect();
    if !cascade_hook::seal_allowed(&phys, &phys) {
        bail!("cascade mismatch");
    }
    let m_stats: Vec<String> = ledger.m.iter().map(|v| online_softmax_ring::fmt6(*v)).collect();
    let ell_stats: Vec<String> = ledger.ell.iter().map(|v| online_softmax_ring::fmt6(*v)).collect();
    let prior_material = blake3_seal_ring::load_prior_material();
    let prior_fold = blake3_seal_ring::prior_fold_hex(&prior_material);
    let compiler_epoch = blake3_seal_ring::load_compiler_epoch();
    let rebuild_nonce = blake3_seal_ring::load_rebuild_nonce();
    let schedule_crc = schedule_mirror::schedule_crc_from_disk();
    let payload = blake3_seal_ring::payload(
        seq_id,
        ledger.run_epoch,
        ledger.pages_resident(),
        &phys,
        ledger.mask_bits,
        &m_stats,
        &ell_stats,
        &prior_fold,
        ledger.compact_gen,
        ledger.visit_checksum,
        ledger.merkle_tip,
        compiler_epoch,
        rebuild_nonce,
        schedule_crc,
        ledger.residue_u64,
    );
    let digest = blake3_seal_ring::digest_hex(&payload);
    let m_json = serde_json::to_string(&m_stats)?;
    let ell_json = serde_json::to_string(&ell_stats)?;
    let body = format!(
        "{{\"seq_id\":{},\"run_epoch\":{},\"tiles_planned\":{},\"pages_resident\":{},\"mask_bits\":{},\"m_stats\":{},\"ell_stats\":{},\"seal_digest\":{}}}",
        serde_json::to_string(seq_id)?,
        ledger.run_epoch,
        ledger.tiles_planned,
        ledger.pages_resident(),
        ledger.mask_bits,
        m_json,
        ell_json,
        serde_json::to_string(&digest)?,
    );
    if let Some(parent) = Path::new(out).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, body)?;
    blake3_seal_ring::persist_prior_seal(&digest)?;
    let mark = seal_trailer::mark(ledger.merkle_tip, profile.spine_salt);
    seal_trailer::persist(mark)?;
    Ok(())
}
