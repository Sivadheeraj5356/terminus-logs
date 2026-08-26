//! Combinatorial Blueprint: residue_u64 seeds from visit_checksum||mask_bits at plan, then
//! parent-chains on every advance with tip/epoch/gen — circular coupling with merkle_tip.
//! Axiomatic Blindspot: seed and rotate axioms are stated; seal fails if residue stays at seed
//! after a successful advance or if replan forgets reseeding.
//! Silent Failure: folding visit_checksum twice instead of residue_u64 into seal_digest.

/// Seed after plan completes visit/mask stats.
pub fn seed(visit_checksum: u32, mask_bits: u32) -> u64 {
    ((visit_checksum as u64) << 32) | (mask_bits as u64)
}

/// Parent-chain after merkle_tip has been updated for this advance.
pub fn chain(prev: u64, run_epoch: u32, compact_gen: u32, merkle_tip: u64) -> u64 {
    prev.rotate_left(7)
        ^ merkle_tip
        ^ (((run_epoch as u64) << 32) | (compact_gen as u64))
}
