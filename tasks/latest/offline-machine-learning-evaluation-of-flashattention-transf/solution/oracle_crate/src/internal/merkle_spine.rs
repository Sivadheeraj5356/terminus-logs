//! Parent-chained residency tip: advance folds SHA-256 into an 8-byte BE tip.
use sha2::{Digest, Sha256};

/// Fold prior tip with epoch, compact_gen, and logical-order physical page ids.
pub fn fold_tip(prior: u64, run_epoch: u32, compact_gen: u32, phys_logical_order: &[u32]) -> u64 {
    let mut hasher = Sha256::new();
    hasher.update(prior.to_be_bytes());
    hasher.update(run_epoch.to_be_bytes());
    hasher.update(compact_gen.to_be_bytes());
    for p in phys_logical_order {
        hasher.update(p.to_le_bytes());
    }
    let dig = hasher.finalize();
    u64::from_be_bytes(dig[..8].try_into().expect("8 bytes"))
}

/// Map entries sorted by logical id → physical ids in seal/spine order.
pub fn phys_logical_order(map: &[(u32, u32)]) -> Vec<u32> {
    let mut pairs = map.to_vec();
    pairs.sort_by_key(|(l, _)| *l);
    pairs.into_iter().map(|(_, p)| p).collect()
}
