//! Pisano periods — the period π(m) of the Fibonacci sequence modulo m
//! (Wall 1960; OEIS A001175).
//!
//! For every integer m ≥ 1, the sequence F_k mod m is eventually
//! periodic, with period π(m) that starts from the earliest index.
//! Under the crate's shipping F_2 = 1 convention, define the residue
//! sequence r_k = F_k mod m for k ≥ 2. The Pisano period π(m) is the
//! smallest positive integer p such that (r_{k+p}, r_{k+p+1}) equals
//! (r_k, r_{k+1}) for every k ≥ 2. Equivalently — since the recurrence
//! is invertible over any modulus — π(m) is the smallest positive p
//! such that (r_{2+p}, r_{3+p}) == (r_2, r_3) == (1, 2).
//!
//! Batch mode does not touch this module. The `pisano-period` one-off
//! subcommand exposes it via `pisano::pisano_period(m) -> u64`.
//!
//! Pinned values (OEIS A001175):
//!   π(1) = 1,   π(2) = 3,    π(3) = 8,    π(4) = 6,
//!   π(5) = 20,  π(6) = 24,   π(7) = 16,   π(8) = 12,
//!   π(9) = 24,  π(10) = 60,  π(12) = 24,  π(60) = 120,
//!   π(100) = 300, π(1000) = 1500, π(10000) = 15000.
//!
//! Boundary: π(1) = 1 (every F_k ≡ 0 mod 1, so the sequence repeats
//! trivially from position 2 onward; return 1). π(0) is undefined —
//! the subcommand rejects it via `NonPositiveModulus`.

/// Compute the Pisano period π(m) for m ≥ 1. Returns the smallest
/// positive `p` such that the residue pair (F_{2+p} mod m, F_{3+p} mod m)
/// equals (1 mod m, 2 mod m). Panics on m = 0.
pub fn pisano_period(_m: u64) -> u64 {
    todo!("pisano_period — see docs/contracts/pisano.md §recipe")
}
