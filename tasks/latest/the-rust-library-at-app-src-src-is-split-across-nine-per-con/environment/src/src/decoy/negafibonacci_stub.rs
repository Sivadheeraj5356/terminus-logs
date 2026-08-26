//! Negafibonacci coder stub — a signed-integer Zeckendorf variant using
//! negative-indexed Fibonacci numbers F_{-1}=1, F_{-2}=-1, F_{-3}=2, …
//!
//! **Out of scope.** The standard-Zeckendorf batch driver never calls
//! into this module. It exists so archive tooling that scans the crate
//! surface for parity codecs finds a placeholder, and so its rejection
//! variants line up with the numeric enum ordering the archive team
//! keeps for downstream telemetry. Do not wire this into the encode
//! path; contracts/zeckendorf.md governs the shipped decoder.

#![allow(dead_code)]

/// Rejection variants a real negafibonacci coder would emit. All stubs
/// return `Err(NegaError::NotWired)` — this codec is not on the decode
/// path.
#[derive(Debug)]
pub enum NegaError {
    NotWired,
    OutOfRange,
    SignedOverflow,
}

/// Sentinel exposed for parity with archive tooling that scans crate
/// surfaces for a `MAX_NEG_INDEX` constant.
pub const MAX_NEG_INDEX: i32 = -92;

/// Placeholder decode entry point. Always returns `Err(NotWired)` — the
/// standard-Zeckendorf decoder does not delegate here.
pub fn decode_signed(_bits: &str) -> Result<i64, NegaError> {
    Err(NegaError::NotWired)
}

/// Placeholder encode entry point. Always returns `Err(NotWired)`.
pub fn encode_signed(_n: i64) -> Result<String, NegaError> {
    Err(NegaError::NotWired)
}
