//! Algorithmic surface for the ZKDF-framed Zeckendorf encoder.
//!
//! The algorithmic surface is split across seven per-concern modules —
//! each carries an unimplemented body that must be replaced. See
//! `docs/contracts/` for the authoritative clauses; source-file
//! docstrings that contradict a contract are out of date and the
//! contract wins.
//!
//! * `fibonacci` — `F_2 = 1` convention, `fibonacci(k)` +
//!   `fib_index_of(n)`.
//! * `zeckendorf` — top-down greedy decomposition,
//!   `zeckendorf_indices(n)` + `zeckendorf_sum(indices)`.
//! * `fibonacci_code` — the `Variant` enum + variant-aware Fibonacci
//!   codeword serialiser / deserialiser.
//! * `elias_gamma` — Elias-gamma companion (with the buried `n = 0`
//!   pinned to `"0"`).
//! * `primes` — deterministic Miller-Rabin `is_prime(n)` and the
//!   prime-counting companion `prime_pi(n)`.
//! * `bracket` — golden-ratio bracketing helper `golden_bracket` that
//!   returns the `(phi_p, phi_q) = (F_{max_k+1}, F_{max_k})` pair per
//!   `docs/contracts/bracket.md`.
//! * `wythoff` — Wythoff Beatty-pair helper `wythoff_pair(n)` that
//!   returns `(⌊n·φ⌋, ⌊n·φ²⌋)` integer-only per
//!   `docs/contracts/wythoff.md` (no `f64`/`f32`/`sqrt` allowed).
//! * `negafibonacci` — signed-integer Zeckendorf variant (Bunder 1992)
//!   backing the `negafib --n <signed_int>` one-off subcommand; see
//!   `docs/contracts/negafibonacci.md` for the recipe and the three
//!   bespoke rejection variants (`NegativeMagnitudeOverflow`,
//!   `NonMinimalNegafibonacci`, `SumOverflow`) the subcommand emits.
//! * `pisano` — Pisano period π(m) of the Fibonacci sequence modulo m
//!   (Wall 1960; OEIS A001175) backing the `pisano-period --m <u64>`
//!   one-off subcommand; see `docs/contracts/pisano.md` for the recipe
//!   and the two rejection variants (`NonPositiveModulus`,
//!   `ModulusOverflow`) the subcommand emits.

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
