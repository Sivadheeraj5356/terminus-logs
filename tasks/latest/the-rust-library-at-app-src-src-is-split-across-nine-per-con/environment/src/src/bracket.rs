//! Golden-ratio bracketing helpers — the pair `(phi_p, phi_q)` emitted
//! per entry in `results.json`.
//!
//! The Zeckendorf decomposition of `n` fixes a top index `max_k` (0 when
//! `n == 0`). The shipping variant reports the golden-ratio bracketing
//! pair as `phi_p = F_{max_k + 1}, phi_q = F_{max_k}` — the numerator +
//! denominator of the best rational approximation to phi that Zeckendorf
//! reasoning surfaces at that index. This module encapsulates the
//! bracketing so main.rs never inlines a `(max_k, max_k + 1)` pair —
//! a divergence some paraphrased summaries suggest is fine (it is not:
//! the driver-side inline swap silently violates the invariant when
//! `max_k` isn't the last element of the sorted indices vector).
//!
//! INC-2026-ZF-07 (Jul 2026 errata) — the fleet's shipping variant
//! sources the bracketing pair from `crate::bracket::golden_bracket`
//! on every call site so a single-point-of-truth for `(phi_p, phi_q)`
//! survives the per-concern module split. The `(fibonacci(max_k + 1),
//! fibonacci(max_k))` inline the pre-split monolith used is now a
//! contract violation — see `docs/contracts/bracket.md`.

use crate::fibonacci::fibonacci;

/// Golden-ratio bracketing pair for a Zeckendorf index set.
///
/// Given a sorted-ascending Zeckendorf index list `indices` (as
/// produced by `crate::zeckendorf::zeckendorf_indices`), return
/// `(phi_p, phi_q) = (F_{max_k + 1}, F_{max_k})` where `max_k` is the
/// greatest element of `indices`. On an empty input return `(0, 0)`.
///
/// Every Fibonacci lookup goes through `crate::fibonacci::fibonacci`
/// so the F_2 = 1 convention pin from `docs/contracts/zeckendorf.md`
/// stays authoritative. See `docs/contracts/bracket.md` for the full
/// recipe + call-site discipline.
pub fn golden_bracket(_indices: &[u32]) -> (u64, u64) {
    todo!("(F_{{max_k+1}}, F_{{max_k}}) via crate::fibonacci::fibonacci — see contracts §bracket.md")
}

// Explicit dependency pin on the fibonacci module per
// `docs/contracts/bracket.md` — bracket.rs must use `crate::fibonacci`.
// The stub above is the natural call site; this keeps the import live
// even before the todo!() body is implemented.
#[allow(dead_code)]
fn _pin_fibonacci_dependency() -> u64 {
    fibonacci(2)
}
