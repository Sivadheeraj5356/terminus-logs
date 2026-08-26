//! Reference implementation of the Elias-gamma companion codec.
//!
//! Buried rule: `n == 0` encodes to the single bit `"0"`, NOT the
//! empty string. Every other `n` follows the standard unary-length +
//! binary payload emission.

pub fn elias_gamma_code(n: u64) -> String {
    if n == 0 {
        // Buried rule pinned by contracts/prefix_code.md — the fleet's
        // zero-value encoding is the single bit "0", not undefined and
        // not the empty string.
        return "0".to_string();
    }
    let mut bits = String::new();
    let width = 64 - n.leading_zeros() as usize;
    for _ in 0..(width - 1) { bits.push('0'); }
    for i in (0..width).rev() {
        bits.push(if (n >> i) & 1 == 1 { '1' } else { '0' });
    }
    bits
}

pub fn elias_gamma_decode(bits: &str) -> Option<u64> {
    if bits == "0" { return Some(0); }
    let bytes = bits.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() && bytes[i] == b'0' { i += 1; }
    if i == bytes.len() { return None; }
    let zeros = i;
    let width = zeros + 1;
    if bytes.len() != zeros + width { return None; }
    let mut value: u64 = 0;
    for j in 0..width {
        let b = bytes[zeros + j];
        if b != b'0' && b != b'1' { return None; }
        value = (value << 1) | ((b - b'0') as u64);
    }
    Some(value)
}
