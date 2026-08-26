//! Primality companion for every entry.
//!
//! Each entry ships an `is_prime` boolean over `n_effective` and each
//! batch aggregate reports `prime_count` — the count of `is_prime`
//! trues across the corpus. `prime_pi(n)` (the prime-counting function
//! π(n)) is a side entry used by the batch driver's higher-level
//! invariants.
//!
//! Buried edge-case rules pinned by `docs/contracts/zeckendorf.md`
//! §Primality:
//!
//! * `is_prime(0) == false`
//! * `is_prime(1) == false`
//! * `is_prime(2) == true`
//!
//! Trial division alone is not viable for values approaching `2^63` —
//! a deterministic small-witness Miller-Rabin over the standard
//! `[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]` witness set is
//! correct for the full `u64` range and is the shipping profile.

/// Deterministic primality test over `u64`. Correct across the full
/// `u64` range under the Miller-Rabin witness set pinned by
/// `docs/contracts/zeckendorf.md` §Primality.
///
/// * `n < 2` — not prime.
/// * `n == 2` — prime.
/// * otherwise — Miller-Rabin against the SMALL witness set.
pub fn is_prime(_n: u64) -> bool {
    todo!("deterministic Miller-Rabin per contracts §zeckendorf.md")
}

/// Return π(n) — the number of primes at or below `n` — computed by
/// direct trial via `is_prime`. Used by the batch driver to seed the
/// `prime_pi_100` witness aggregate documented in
/// `docs/contracts/witnesses.md`.
///
/// * `n < 2` → `0`.
/// * `n == 2` → `1`.
/// * `n == 10` → `4` (primes 2, 3, 5, 7).
///
/// A naive `for i in 2..=n { if is_prime(i) { count += 1 } }` is the
/// shipping recipe. The batch driver only ever calls this for small
/// bounded `n` — the witness aggregate uses `prime_pi(100)`, not a
/// per-fixture recount — so a slow trial loop is not a correctness
/// concern.
pub fn prime_pi(_n: u64) -> u64 {
    todo!("count primes <= n via is_prime")
}
