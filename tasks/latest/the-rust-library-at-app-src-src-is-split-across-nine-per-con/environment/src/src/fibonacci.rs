//! Fibonacci sequence under the shipping F_2 = 1 convention.
//!
//! Two entry points on the shipping surface:
//!
//! * `fibonacci(k)` — the k-th Fibonacci number under the Zeckendorf
//!   convention pinned by `docs/contracts/zeckendorf.md` §Fibonacci
//!   convention. `k` starts at 2 (`F_2 = 1`, `F_3 = 2`, `F_4 = 3`,
//!   `F_5 = 5`, ...). Panics on `k < 2`.
//! * `fib_index_of(n)` — the greatest `k >= 2` such that
//!   `fibonacci(k) <= n`, or `None` when `n < 1`. Used by the greedy
//!   Zeckendorf decomposition to locate the top index without repeated
//!   trial calls into `fibonacci`.
//!
//! The BCH- / textbook-style `F_0 = 0, F_1 = 1, F_2 = 1, F_3 = 2, ...`
//! convention is **wrong** for this crate — a decoder that seeds
//! `(a, b) = (0, 1)` and returns `b` at step `k` produces every fixture's
//! `zeckendorf_indices` off by one.

/// Return `F_k` under the shipping F_2 = 1 convention.
///
/// See `docs/contracts/zeckendorf.md` §Fibonacci convention. Panics
/// on `k < 2` — F_0 and F_1 do not exist in this convention.
pub fn fibonacci(_k: u32) -> u64 {
    todo!("return the k-th Fibonacci per the contract's F_2 = 1 convention")
}

/// Return the greatest `k >= 2` such that `fibonacci(k) <= n`, or
/// `None` when `n < 1` (there is no Fibonacci index at or below `0`
/// under this convention).
///
/// Callers use this to locate the top index for the top-down greedy
/// Zeckendorf decomposition without a linear scan through
/// `fibonacci(2..)`. See `docs/contracts/zeckendorf.md` §Zeckendorf
/// decomposition.
pub fn fib_index_of(_n: u64) -> Option<u32> {
    todo!("return the greatest k >= 2 with fibonacci(k) <= n")
}
