/// Cold-side text hashing for offline tooling (decoy path).
pub fn warm_digest(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0u64, |a, b| a.wrapping_add(u64::from(*b)))
}
