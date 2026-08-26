//! Variant-aware Fibonacci codeword serialisation.
//!
//! The `Variant` enum lives here and nowhere else on the algorithmic
//! surface. The two variants share the Zeckendorf index set produced
//! by `crate::zeckendorf::zeckendorf_indices`; they differ only in the
//! bit ordering of the emitted codeword.
//!
//! * `Variant::Canonical` (marker byte `0x00`) — MSB-first ordering as
//!   pinned by `docs/contracts/prefix_code.md` §Fibonacci code. Bit
//!   position `i` (0-indexed) corresponds to Fibonacci index `i + 2`;
//!   the terminating `'1'` sits at position `max_k - 1`.
//! * `Variant::ReverseMsb` (marker byte `0x01`) — the rotation's
//!   in-house LSB-first ordering pinned by `docs/contracts/variants.md`.
//!   Same Zeckendorf index set, same codeword length, same set of `'1'`
//!   bits — but reversed end-for-end so the terminating pair sits at
//!   the FRONT of the string.
//!
//! A decoder that ignores the variant byte and emits every codeword
//! MSB-first passes canonical fixtures but fails every reverse-msb
//! fixture with the wrong bit string. See
//! `docs/contracts/variants.md` for the variant table and
//! `docs/contracts/prefix_code.md` for the canonical layout.
//!
//! This module composes with `crate::zeckendorf` — the decode-side
//! helper `fibonacci_decode_n(bits, variant)` returns the underlying
//! integer by chaining `fibonacci_decode` into
//! `crate::zeckendorf::zeckendorf_sum`. The module-import discipline
//! is enforced by `test_fibonacci_code_module_imports_zeckendorf`.

use crate::zeckendorf::zeckendorf_sum;

/// Encoding-variant profile — pinned by `docs/contracts/variants.md`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Variant {
    /// MSB-first canonical Fibonacci coding (marker byte `0x00`).
    Canonical,
    /// LSB-first rotation-profile Fibonacci coding (marker byte `0x01`).
    ReverseMsb,
}

impl Variant {
    /// Human-facing label used in the canonical JSON `variant` field
    /// per `docs/contracts/variants.md`.
    pub fn label(self) -> &'static str {
        match self {
            Variant::Canonical => "canonical",
            Variant::ReverseMsb => "reverse-msb",
        }
    }
}

/// Serialise the Fibonacci codeword for `indices` under
/// `Variant::Canonical`. Equivalent to
/// `fibonacci_code_variant(indices, Variant::Canonical)`.
pub fn fibonacci_code(_indices: &[u32]) -> String {
    todo!("canonical Fibonacci codeword per contracts §prefix_code.md")
}

/// Serialise the Fibonacci codeword for `indices` under the given
/// variant. Reverse-msb reverses the canonical bit string end-for-end
/// per `docs/contracts/variants.md`.
pub fn fibonacci_code_variant(_indices: &[u32], _variant: Variant) -> String {
    todo!("variant-aware Fibonacci codeword per contracts §variants.md")
}

/// Invert a variant-aware Fibonacci codeword back to its Zeckendorf
/// index list. Returns `None` when the bit string is malformed under
/// the given variant (no terminating pair, mismatched length, etc.).
///
/// The round-trip identity
/// `fibonacci_decode(&fibonacci_code_variant(&idx, v), v) == Some(idx)`
/// holds for every valid `idx`, `v` pair. This function participates
/// in the crate's decode-side surface and is exercised by the
/// `roundtrip_witness` proof plane emitted from the batch driver — see
/// `docs/contracts/roundtrip.md` for the plane's derivation.
pub fn fibonacci_decode(_bits: &str, _variant: Variant) -> Option<Vec<u32>> {
    todo!("invert fibonacci_code_variant per contracts §variants.md")
}

/// Composed decode helper — parse `bits` under `variant`, then recover
/// the underlying integer via `crate::zeckendorf::zeckendorf_sum`.
///
/// Returns `None` when the bit string is malformed. Well-formed input
/// satisfies the round-trip identity
/// `fibonacci_decode_n(&fibonacci_code_variant(&idx, v), v) == Some(zeckendorf_sum(&idx))`.
/// See `docs/contracts/roundtrip.md` §Composed decoder for the fleet
/// wiring notes.
pub fn fibonacci_decode_n(_bits: &str, _variant: Variant) -> Option<u64> {
    todo!("compose fibonacci_decode + crate::zeckendorf::zeckendorf_sum per contracts §roundtrip.md")
}

// Explicit dependency on the zeckendorf module per
// `docs/contracts/roundtrip.md` — `fibonacci_code.rs` must use
// `crate::zeckendorf::` for the composed decoder. The composed
// `fibonacci_decode_n` above is the natural call site; this pin keeps
// the import live even before the todo!() body is implemented.
#[allow(dead_code)]
fn _pin_zeckendorf_dependency() -> u64 {
    zeckendorf_sum(&[])
}
