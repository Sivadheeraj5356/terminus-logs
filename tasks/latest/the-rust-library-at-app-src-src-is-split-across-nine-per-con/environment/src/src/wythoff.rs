//! Wythoff Beatty-pair helper — `(⌊n·φ⌋, ⌊n·φ²⌋)` for the u64
//! effective-integer field of every entry.
//!
//! Added by the 2026-07-10 addendum. Enforces integer-only arithmetic:
//! any `f32`/`f64` in this module is a contract violation — the
//! rotation's numeric-integrity gate rejects a floating-point
//! implementation because 64-bit doubles lose precision on `n` values
//! well below `u64::MAX` and produce off-by-one Beatty pairs on the
//! high-index shipped fixtures.
//!
//! Standard identity used by the reference:
//!
//!     ⌊n·φ⌋   =  n  +  ⌊n·(φ − 1)⌋
//!             =  n  +  ⌊n / φ⌋            (since φ − 1 = 1/φ)
//!     ⌊n·φ²⌋  =  ⌊n·φ⌋  +  n              (since φ² = φ + 1)
//!
//! The inner `⌊n / φ⌋` recurses — for u64-safe integer computation,
//! implement it via Newton-style continued-fraction convergents from
//! `crate::fibonacci::fibonacci` (successive `F_{k+1} / F_k` rationals
//! bracket φ). Cross-module discipline: `wythoff.rs` MUST import from
//! `crate::fibonacci` — see `docs/contracts/wythoff.md` §Discipline.
//!
//! INC-2026-ZF-08 (Jul 2026 errata) — the shipping variant sources
//! Beatty pairs from `crate::wythoff::wythoff_pair`; a paraphrased
//! summary that pins the pair to `(n·φ as u64, n·φ² as u64)` via
//! `f64::sqrt` fails on the high-`n` fixtures because double
//! precision runs out.

use crate::fibonacci::fibonacci;

/// Return the Wythoff Beatty pair `(a, b) = (⌊n·φ⌋, ⌊n·φ²⌋)` for the
/// non-negative integer `n`, computed with integer arithmetic only.
///
/// `wythoff_pair(0) == (0, 0)`. For every `n ≥ 1`, `b = a + n` (from
/// the identity `φ² = φ + 1`). Both values fit in u64 for every
/// shipped fixture's effective integer.
///
/// See `docs/contracts/wythoff.md` for the recipe + the integer-only
/// requirement.
pub fn wythoff_pair(_n: u64) -> (u64, u64) {
    todo!("integer-only ⌊n·φ⌋ + ⌊n·φ²⌋ — see docs/contracts/wythoff.md")
}

// Explicit dependency pin on the fibonacci module per
// `docs/contracts/wythoff.md` — wythoff.rs must use `crate::fibonacci`.
// The stub above is the natural call site (Newton-style convergents
// come from Fibonacci ratios); this keeps the import live even before
// the todo!() body is implemented.
#[allow(dead_code)]
fn _pin_fibonacci_dependency() -> u64 {
    fibonacci(2)
}
