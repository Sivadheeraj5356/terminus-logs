//! Combinatorial Blueprint: visit_checksum XOR-folds mask-kept (h,qi,kj) visits during plan.
//! Axiomatic Blindspot: pages_resident = n_heads×n_k while visit_checksum only sees kept pairs.
//! Silent Failure Point: undercounting unique kj or overcounting unmasked pairs desyncs ell and checksum.

/// Fold one mask-kept schedule visit into the running XOR custody.
pub fn fold_visit(acc: u32, h: u32, qi: u32, kj: u32) -> u32 {
    acc ^ (((h << 16) | (qi << 8) | kj) & 0xffff_ffff)
}
