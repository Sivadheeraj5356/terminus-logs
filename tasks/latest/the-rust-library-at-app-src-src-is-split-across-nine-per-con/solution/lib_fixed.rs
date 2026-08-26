//! Algorithmic surface — reference lib.rs.
//!
//! Mirrors the seed module split. Every real implementation lives in
//! its per-concern *_fixed.rs sibling; this file only carries the
//! `pub mod` declarations and re-exports.

pub mod bracket;
pub mod decoy;
pub mod elias_gamma;
pub mod fibonacci;
pub mod fibonacci_code;
pub mod negafibonacci;
pub mod pisano;
pub mod primes;
pub mod wythoff;
pub mod zeckendorf;

pub use bracket::golden_bracket;
pub use elias_gamma::{elias_gamma_code, elias_gamma_decode};
pub use fibonacci::{fib_index_of, fibonacci};
pub use fibonacci_code::{
    fibonacci_code, fibonacci_code_variant, fibonacci_decode, Variant,
};
pub use negafibonacci::{
    negafib_abs, negafib_indices, negafib_is_minimal, negafib_sum, negafib_value,
};
pub use pisano::pisano_period;
pub use primes::{is_prime, prime_pi};
pub use wythoff::wythoff_pair;
pub use zeckendorf::{zeckendorf_indices, zeckendorf_sum};
