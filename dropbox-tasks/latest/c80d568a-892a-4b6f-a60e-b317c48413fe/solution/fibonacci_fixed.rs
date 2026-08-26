//! Reference implementation of the Fibonacci module.
//!
//! Shipping convention: `F_2 = 1`, `F_3 = 2`, `F_4 = 3`, `F_5 = 5`,
//! `F_k = F_{k-1} + F_{k-2}` for `k >= 4`. `F_0` and `F_1` do not
//! exist under this convention — `fibonacci(k)` panics on `k < 2`.

pub fn fibonacci(k: u32) -> u64 {
    assert!(k >= 2, "Fibonacci indices are >= 2 in this convention");
    let mut a: u64 = 1;  // F_2
    let mut b: u64 = 2;  // F_3
    if k == 2 { return a; }
    if k == 3 { return b; }
    for _ in 4..=k {
        let c = a + b;
        a = b;
        b = c;
    }
    b
}

/// Return the greatest `k >= 2` with `fibonacci(k) <= n`, or `None`
/// when `n < 1`. Walks `fibonacci` values monotonically; halts before
/// overflow.
pub fn fib_index_of(n: u64) -> Option<u32> {
    if n < 1 { return None; }
    let mut k: u32 = 2;
    // grow k while fibonacci(k + 1) still fits and <= n
    loop {
        let next = k + 1;
        // compute fibonacci(next) without a fresh call each step
        // (fresh call is fine here — corpus range is bounded)
        let f_next = fibonacci(next);
        if f_next > n { break; }
        k = next;
        // avoid overflow at the u64 ceiling
        if next >= 92 { break; }
    }
    Some(k)
}
