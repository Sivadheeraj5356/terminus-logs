//! Negafibonacci coding — signed-integer Zeckendorf variant.
//!
//! Crate convention: `F_2 = 1, F_3 = 2, F_4 = 3, F_5 = 5, …` (no F_0
//! or F_1 under the shipping Fibonacci convention — see
//! `docs/contracts/zeckendorf.md`). Negafibonacci extends this to
//! signed integers using the identity `F_{-k} = (-1)^{k+1} · |F_k|`
//! for `k ≥ 1`, with `|F_1| = 1` treated as the boundary value
//! (equal to `crate::fibonacci::fibonacci(2)`).
//!
//! Every non-zero signed integer has a unique canonical negafibonacci
//! representation as a strictly-ascending, non-adjacent list of
//! positive indices `k`. Zero is the empty list. See
//! `docs/contracts/negafibonacci.md` for the recipe (greedy
//! magnitude-and-sign selection + Bunder collapse `F_{-k} + F_{-(k+1)}
//! = F_{-(k-1)}`) and the three rejection variants surfaced through
//! the batch driver's `negafib` subcommand.

/// Magnitude of `F_{-k}` for `k ≥ 1`. Delegates to `crate::fibonacci`
/// for `k ≥ 2`; `|F_{-1}| = 1` is the boundary value.
pub fn negafib_abs(_k: u32) -> i64 {
    todo!("negafib_abs — see docs/contracts/negafibonacci.md §values")
}

/// Signed value of `F_{-k}` for `k ≥ 1`. Negative for even `k`.
pub fn negafib_value(_k: u32) -> i64 {
    todo!("negafib_value — see docs/contracts/negafibonacci.md §values")
}

/// Greedy negafibonacci decomposition of `n`. Returns the sorted,
/// non-adjacent list of indices whose signed F-values sum to `n`.
/// Zero returns `vec![]`.
pub fn negafib_indices(_n: i64) -> Vec<u32> {
    todo!("negafib_indices — see docs/contracts/negafibonacci.md §recipe")
}

/// Reconstruct the signed integer from a list of negafibonacci
/// indices. Returns 0 for an empty vector.
pub fn negafib_sum(_indices: &[u32]) -> i64 {
    todo!("negafib_sum — see docs/contracts/negafibonacci.md §reconstruct")
}

/// Check that `indices` is canonical negafibonacci form:
/// strictly ascending AND no two consecutive integers.
pub fn negafib_is_minimal(_indices: &[u32]) -> bool {
    todo!("negafib_is_minimal — see docs/contracts/negafibonacci.md §canonical")
}
