//! Stdout line hasher for support tooling (non-authority).

pub fn hash_line(line: &str) -> u64 {
    let mut h: u64 = 0x811c_9dc5;
    for b in line.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0100_0193);
    }
    h
}
