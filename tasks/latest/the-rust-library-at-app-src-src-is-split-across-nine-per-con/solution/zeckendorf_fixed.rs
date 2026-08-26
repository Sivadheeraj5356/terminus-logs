//! Reference implementation of the Zeckendorf module.
//!
//! Top-down greedy: locate the largest `F_k <= n`, subtract, skip
//! index `k - 1` (non-consecutive invariant), continue from `k - 2`.
//! Result sorted ascending. Every Fibonacci lookup goes through
//! `crate::fibonacci::fibonacci` — no Fibonacci value is hardcoded.

use crate::fibonacci::{fib_index_of, fibonacci};

pub fn zeckendorf_indices(n: u64) -> Vec<u32> {
    if n == 0 { return vec![]; }
    let top = match fib_index_of(n) {
        Some(k) => k,
        None => return vec![],
    };
    let mut remaining = n;
    let mut used: Vec<u32> = Vec::new();
    let mut cur = top;
    loop {
        let f = fibonacci(cur);
        if f <= remaining {
            used.push(cur);
            remaining -= f;
            if cur == 2 { break; }
            cur -= 2;
        } else {
            if cur == 2 { break; }
            cur -= 1;
        }
        if remaining == 0 { break; }
    }
    used.sort();
    used
}

pub fn zeckendorf_sum(indices: &[u32]) -> u64 {
    let mut total: u64 = 0;
    for &k in indices {
        total = total.wrapping_add(fibonacci(k));
    }
    total
}
