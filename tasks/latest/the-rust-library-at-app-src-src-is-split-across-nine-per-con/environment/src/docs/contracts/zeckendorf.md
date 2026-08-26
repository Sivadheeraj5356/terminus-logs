# zeckendorf.md — redirect + primality clauses

Split on 2026-07-08. The Zeckendorf decomposition and canonical-form
clauses now live in sibling files under `/app/src/docs/contracts/`:

- `decomposition.md` — `F_2 = 1` Fibonacci convention, `fibonacci(k)`
  (panics on `k < 2`), `fib_index_of`, top-down greedy
  `zeckendorf_indices`, `zeckendorf_sum`, anti-hardcode rule.
- `canonical.md` — ascending index ordering, non-consecutive
  invariant, empty-case pinning, round-trip identity that feeds
  `roundtrip.md`.

Primality clauses stay attached to this file — they are the entry
condition for `is_prime` in every emitted entry.

## Primality

`is_prime(n)` on `u64`. Buried edge-case rules:

* `is_prime(0) == false`
* `is_prime(1) == false`
* `is_prime(2) == true`

Trial division alone is not viable for values approaching `2^63`; a
deterministic small-witness Miller-Rabin over
`[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]` is correct for the full
`u64` range and is the shipping profile. Magic-mismatch entries and
unknown-variant entries emit `is_prime = false` unconditionally (their
`n_effective` is pinned to `0` — see `variants.md`).

`prime_pi(n)` counts primes at or below `n` by direct trial via
`is_prime`. Used by the batch driver to seed the `prime_pi_100`
witness aggregate — `prime_pi(100) == 25`. See `witnesses.md`.

## Golden-ratio pair

For every entry with a non-empty Zeckendorf decomposition, let
`k = max(zeckendorf_indices)`:

    phi_p = fibonacci(k + 1)
    phi_q = fibonacci(k)

For an empty Zeckendorf list, `phi_p = phi_q = 0`.
