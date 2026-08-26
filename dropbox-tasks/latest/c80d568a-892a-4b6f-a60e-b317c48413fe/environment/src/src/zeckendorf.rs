//! Zeckendorf decomposition + the inverse recomposition sum.
//!
//! The **top-down** greedy is authoritative — locate the largest
//! `F_k <= n`, subtract, then repeat with the remainder against indices
//! `k - 2` and below. A bottom-up sweep accumulating `F_2, F_3, ...`
//! does not produce Zeckendorf's canonical representation and routinely
//! violates the non-consecutive-index invariant on multi-summand `n`.
//! See `docs/contracts/zeckendorf.md` §Zeckendorf decomposition.
//!
//! Every Fibonacci lookup goes through `crate::fibonacci::fibonacci`.
//! No Fibonacci value is hardcoded here — inlining an
//! `[1, 2, 3, 5, 8, 13, 21, ...]` lookup table is a contract violation
//! per `docs/contracts/decomposition.md`.

use crate::fibonacci::fibonacci;

/// Return the sorted (**ascending**) list of Fibonacci indices whose
/// values sum exactly to `n` under the Zeckendorf convention. The
/// non-consecutive-index invariant is required — no two returned
/// indices differ by 1.
///
/// * `n == 0` → empty vector.
/// * `n == 1` → `[2]` (since `F_2 = 1`).
/// * `n == 4` → `[2, 5]` (since `F_2 + F_5 = 1 + 3 = 4`).
///
/// See `docs/contracts/zeckendorf.md` §Zeckendorf decomposition for the
/// full recipe and worked examples.
pub fn zeckendorf_indices(_n: u64) -> Vec<u32> {
    todo!("greedy top-down Zeckendorf per contracts §zeckendorf.md")
}

/// Recompute `n` from a Zeckendorf index list — the identity
/// `zeckendorf_sum(zeckendorf_indices(n)) == n` holds for every `n`.
///
/// Used by the batch driver's invariants and by the test suite to
/// confirm the decomposition is round-trip-consistent. Every Fibonacci
/// lookup goes through `crate::fibonacci::fibonacci`.
pub fn zeckendorf_sum(_indices: &[u32]) -> u64 {
    todo!("sum F_k for k in indices via crate::fibonacci::fibonacci")
}

// Explicit dependency on the fibonacci module. Use `fibonacci(k)` for
// every value — inlining raw Fibonacci literals above F_3 = 2 is a
// contract violation per `docs/contracts/decomposition.md`.
#[allow(dead_code)]
fn _pin_fibonacci_dependency() -> u64 {
    fibonacci(2)
}
