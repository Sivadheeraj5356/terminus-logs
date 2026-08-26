//! Reference implementation of the variant-aware Fibonacci codec.
//!
//! * `Variant::Canonical` — MSB-first ordering, terminating `'1'` at
//!   the tail (positions `k - 2` for each `k` in indices are `'1'`).
//! * `Variant::ReverseMsb` — reverse the canonical string end-for-end.
//!   Same length, same `'1'` count, opposite ordering.
//!
//! The composed decoder `fibonacci_decode_n` closes the round-trip loop
//! by chaining `fibonacci_decode` into
//! `crate::zeckendorf::zeckendorf_sum` — the batch driver's
//! `roundtrip_witness` proof plane consumes it per
//! `docs/contracts/roundtrip.md`.

use crate::zeckendorf::zeckendorf_sum;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Variant {
    Canonical,
    ReverseMsb,
}

impl Variant {
    pub fn label(self) -> &'static str {
        match self {
            Variant::Canonical => "canonical",
            Variant::ReverseMsb => "reverse-msb",
        }
    }
}

fn canonical_bits(indices: &[u32]) -> String {
    if indices.is_empty() { return String::new(); }
    let max_k = *indices.iter().max().unwrap();
    let len = max_k as usize;
    let mut bits = vec![b'0'; len];
    for &k in indices {
        bits[(k - 2) as usize] = b'1';
    }
    bits[(max_k - 1) as usize] = b'1';
    String::from_utf8(bits).unwrap()
}

pub fn fibonacci_code(indices: &[u32]) -> String {
    canonical_bits(indices)
}

pub fn fibonacci_code_variant(indices: &[u32], variant: Variant) -> String {
    let canonical = canonical_bits(indices);
    match variant {
        Variant::Canonical => canonical,
        Variant::ReverseMsb => canonical.chars().rev().collect(),
    }
}

pub fn fibonacci_decode(bits: &str, variant: Variant) -> Option<Vec<u32>> {
    if bits.is_empty() { return Some(vec![]); }
    let canonical: String = match variant {
        Variant::Canonical => bits.to_string(),
        Variant::ReverseMsb => bits.chars().rev().collect(),
    };
    let bytes = canonical.as_bytes();
    // Canonical form must end with '1' and each earlier position i
    // holding '1' contributes index i + 2 to the result.
    if !bytes.last().map(|c| *c == b'1').unwrap_or(false) {
        return None;
    }
    let len = bytes.len();
    let mut indices: Vec<u32> = Vec::new();
    // positions 0 .. len - 2 hold the data bits (index i + 2)
    for i in 0..len.saturating_sub(1) {
        match bytes[i] {
            b'1' => indices.push((i + 2) as u32),
            b'0' => {}
            _ => return None,
        }
    }
    // terminating '1' at position len - 1 corresponds to index len + 1
    // — but this same index MUST already have been recorded at position
    // len - 2 for a well-formed canonical codeword.
    if len >= 2 && bytes[len - 2] != b'1' {
        return None;
    }
    indices.sort();
    Some(indices)
}

/// Composed decoder: parse `bits` under `variant` and recover the
/// underlying integer via `crate::zeckendorf::zeckendorf_sum`. The
/// batch driver uses this to close the `roundtrip_witness` loop —
/// see `docs/contracts/roundtrip.md` for the plane's derivation.
pub fn fibonacci_decode_n(bits: &str, variant: Variant) -> Option<u64> {
    fibonacci_decode(bits, variant).map(|idx| zeckendorf_sum(&idx))
}
