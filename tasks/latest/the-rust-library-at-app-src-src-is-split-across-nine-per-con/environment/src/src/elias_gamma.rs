//! Elias-gamma companion codec.
//!
//! Each Zeckendorf-coded fixture ships an Elias-gamma companion emitted
//! from the same `n_effective`. The two codewords travel side-by-side
//! in every entry so downstream consumers that only understand one of
//! the two universal codes still validate.
//!
//! Buried rule (`docs/contracts/prefix_code.md` §Elias gamma): the fleet
//! pins the `n == 0` encoding to the single bit `"0"` — NOT the empty
//! string that the textbook Elias-gamma is undefined for. This shows up
//! in every fixture whose `n_effective` collapses to zero (bad-magic
//! fixtures, unknown-variant fixtures).

/// Return the Elias-gamma codeword for `n` under the shipping profile.
///
/// * `n == 0` — the buried rule pins the codeword to the single bit
///   `"0"`. See `docs/contracts/prefix_code.md` §Elias gamma.
/// * `n >= 1` — let `w = floor(log2(n)) + 1`. Emit `w - 1` zeros
///   followed by the binary of `n` MSB-first, starting with its
///   leading `'1'`. Total length is `2 * w - 1`.
pub fn elias_gamma_code(_n: u64) -> String {
    todo!("Elias-gamma per contracts §prefix_code.md (n=0 pinned to \"0\")")
}

/// Invert an Elias-gamma codeword back to its integer. Returns `None`
/// on malformed input.
///
/// The round-trip identity
/// `elias_gamma_decode(&elias_gamma_code(n)) == Some(n)` holds for
/// every `n`, including the `n = 0` boundary. This function is not
/// called by the batch driver on shipping fixtures — it participates
/// in the crate's decode-side surface.
pub fn elias_gamma_decode(_bits: &str) -> Option<u64> {
    todo!("invert elias_gamma_code per contracts §prefix_code.md")
}
