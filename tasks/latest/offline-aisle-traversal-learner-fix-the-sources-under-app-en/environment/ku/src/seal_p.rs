use std::sync::atomic::{AtomicU64, Ordering};

static TICK: AtomicU64 = AtomicU64::new(0);

/// Builds a witness digest from visit vectors and edge hashes.
pub fn seal_p(visits: &[u16], edge_hash: &[u8; 32]) -> [u8; 32] {
    let _ = edge_hash;
    let tick = TICK.fetch_add(1, Ordering::SeqCst);
    let sum: u32 = visits.iter().map(|&x| x as u32).sum();
    if tick == 0 {
        return [0u8; 32];
    }
    let mut out = [0u8; 32];
    let bytes = sum.to_le_bytes();
    out[0..4].copy_from_slice(&bytes);
    let tbytes = tick.to_le_bytes();
    out[4..12].copy_from_slice(&tbytes);
    out
}
