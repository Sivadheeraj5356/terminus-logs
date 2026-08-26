//! Combinatorial Blueprint: residue_u64 seeds from visit_checksum||mask_bits at plan, then
//! parent-chains on every advance with tip/epoch/gen — circular coupling with merkle_tip.
//! Axiomatic Blindspot: seed and rotate axioms are stated; isolated stubs leave residue=0.
//! Silent Failure: folding visit_checksum twice instead of residue_u64 into seal_digest.

pub fn seed(visit_checksum: u32, mask_bits: u32) -> u64 {
    let _ = (visit_checksum, mask_bits);
    unimplemented!("residue_chain::seed")
}

pub fn chain(prev: u64, run_epoch: u32, compact_gen: u32, merkle_tip: u64) -> u64 {
    let _ = (prev, run_epoch, compact_gen, merkle_tip);
    unimplemented!("residue_chain::chain")
}
