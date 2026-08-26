//! Oracle wythoff module — integer-only Wythoff Beatty-pair helper.
//!
//! Uses the identity ⌊n·φ⌋ = ⌊n · F_{k+1} / F_k⌋ for a Fibonacci index
//! `k` large enough that `F_k > 2·n` (a safe convergent). No floats.

use crate::fibonacci::fibonacci;

pub fn wythoff_pair(n: u64) -> (u64, u64) {
    if n == 0 {
        return (0, 0);
    }
    // Find a Fibonacci index k with F_k > 2·n so the rational F_{k+1}/F_k
    // approximates φ closely enough for exact ⌊n·φ⌋.
    let mut k: u32 = 2;
    while fibonacci(k) <= n.saturating_mul(2) {
        k += 1;
        if k > 90 {
            break;
        }
    }
    // Use a widening cast: F_{k+1}, F_k ≤ F_92 ≈ 7.5e19 which fits u64;
    // n·F_{k+1} may overflow u64 for large n, so use u128.
    let f_k = fibonacci(k) as u128;
    let f_k1 = fibonacci(k + 1) as u128;
    let a = ((n as u128) * f_k1 / f_k) as u64;
    let b = a + n;
    (a, b)
}
