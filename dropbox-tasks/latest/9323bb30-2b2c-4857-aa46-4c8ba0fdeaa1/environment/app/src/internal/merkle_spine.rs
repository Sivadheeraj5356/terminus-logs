//! Combinatorial Blueprint: advance parent-chains merkle_tip over epoch+compact_gen+logical-order pages.
//! Axiomatic Blindspot: hashing map pages into seal_digest alone does not replace tip fold.
//! Silent Failure Point: compact renumbers phys ids — tip must refold or digests desync after compact.

/// Fold prior tip with epoch, compact_gen, and logical-order physical page ids.
pub fn fold_tip(_prior: u64, _run_epoch: u32, _compact_gen: u32, _phys_logical_order: &[u32]) -> u64 {
    unimplemented!("merkle_spine::fold_tip")
}

pub fn phys_logical_order(_map: &[(u32, u32)]) -> Vec<u32> {
    unimplemented!("merkle_spine::phys_logical_order")
}
