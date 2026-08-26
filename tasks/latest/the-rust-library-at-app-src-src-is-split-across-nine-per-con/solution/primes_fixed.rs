//! Reference implementation of the primality companion.
//!
//! Deterministic Miller-Rabin over the SMALL witness set — correct
//! across the full u64 range. `prime_pi(n)` for the batch driver's
//! witness aggregate.

pub fn is_prime(n: u64) -> bool {
    if n < 2 { return false; }
    const SMALL: [u64; 12] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    for &p in SMALL.iter() {
        if n == p { return true; }
        if n % p == 0 { return false; }
    }
    let mut d = n - 1;
    let mut r: u32 = 0;
    while d & 1 == 0 { d >>= 1; r += 1; }
    'outer: for &a in SMALL.iter() {
        if a >= n { continue; }
        let mut x = mod_pow(a, d, n);
        if x == 1 || x == n - 1 { continue; }
        for _ in 0..(r - 1) {
            x = mod_mul(x, x, n);
            if x == n - 1 { continue 'outer; }
        }
        return false;
    }
    true
}

pub fn prime_pi(n: u64) -> u64 {
    let mut count = 0u64;
    let mut i: u64 = 2;
    while i <= n {
        if is_prime(i) { count += 1; }
        i += 1;
    }
    count
}

fn mod_mul(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

fn mod_pow(mut base: u64, mut exp: u64, m: u64) -> u64 {
    if m == 1 { return 0; }
    let mut result: u64 = 1;
    base %= m;
    while exp > 0 {
        if exp & 1 == 1 { result = mod_mul(result, base, m); }
        exp >>= 1;
        if exp > 0 { base = mod_mul(base, base, m); }
    }
    result
}
