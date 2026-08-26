# wythoff.md — Wythoff Beatty-pair proof plane

Added by the 2026-07-10 addendum. Every entry in `decoded` picks up a
Wythoff Beatty pair `(a, b)` derived from its `n` field. The pair
folds into the sixth witness plane — `wythoff_witness`.

## Recipe

`crate::wythoff::wythoff_pair(n) -> (u64, u64)` is the single-point
entry that returns the pair for each entry's `n_effective` field.

For each non-negative integer `n`, `wythoff_pair(n)` returns `(a, b)`
computed by the following pinned recipe:

- Find `k`, the smallest Fibonacci index (under the F_2=1 convention)
  such that `F_k > 2·n`. Use `n.saturating_mul(2)` for the comparison
  so the search terminates near `u64::MAX`; cap `k` at 90 as a safety
  bound (F_92 ≈ 7.5×10^19 covers the whole u64 range).
- `a = ((n as u128) * F_{k+1} / F_k) as u64` — widening multiplication
  to u128, integer divide by `F_k`, then narrowing cast to u64 (masks
  to the low 64 bits). Fixtures with mathematical `n · φ ≥ 2^64` land
  on the low-64-bit wrap of the true value.
- `b = a.wrapping_add(n)` — the u64-wrapping sum. Equivalent to
  `⌊n · φ²⌋` when the true value fits u64; otherwise the u64-wrapped
  low-64-bit value.
- `n = 0` returns `(0, 0)`.

Overflow-semantics are load-bearing. A u64-only implementation that
uses `wrapping_mul` on `n * F_{k+1}` BEFORE dividing produces a
fundamentally different result than the widening path — the widening
to u128 (or wider) before the divide is NOT optional. The
Zeckendorf-identity route `⌊n · φ⌋ = Σ F_{k_i+1}` for the Zeckendorf
indices of `n` is mathematically equivalent to the convergent recipe,
but the accumulator MUST also be at least u128 (or use `wrapping_add`
so the sum mod 2^64 matches the u128-then-truncate result of the
convergent path).

## Integer-only requirement

The reference implementation MUST compute both values with integer
arithmetic — no `f32`, no `f64`, no `.sqrt(`. Rationale: `f64` runs
out of mantissa precision on fixtures whose XOR-decoded `n` exceeds
`2^52`, and a floating-point implementation yields off-by-one `a`
values on those.

Standard integer routes:

- Newton-style convergents from `crate::fibonacci::fibonacci` — the
  ratios `F_{k+1} / F_k` bracket φ, so `⌊n · φ⌋` can be computed as
  `⌊n · F_{k+1} / F_k⌋` for a sufficiently large `k` (a `k` where
  `F_k` exceeds `2 · n` is safe on this corpus).
- The identity `⌊n · φ⌋ = n + ⌊n / φ⌋` with `⌊n / φ⌋ = ⌊n · (φ − 1)⌋`
  applied recursively over a Fibonacci-based rational approximation of
  `φ − 1`.

Either route requires `wythoff.rs` to use the shared `crate::fibonacci`
module for Fibonacci lookups.

## Projection

    wythoff_records = sorted(
        [ {"a": <u64>, "b": <u64>, "name": "<stem>"}
          for every entry in decoded ],
        key = "name"
    )
    wythoff_witness = SHA-256( canonical_json(wythoff_records) )

Canonical JSON: keys sorted lex at every depth (`a < b < name`), no
whitespace between tokens, no trailing newline.

## Cross-module discipline

`wythoff.rs` MUST use the shared `crate::fibonacci` module for
Fibonacci lookups. A module that inlines the Fibonacci recurrence
locally OR reaches for `f64::sqrt` diverges from this contract.

## Position in `chain_sha256`

`wythoff_witness` lands LEX-LAST among the six witness planes
(`codeword < policy < roundtrip < salt < variant < wythoff`). See
`witnesses.md §chain_sha256` for the concatenation.

## Not per-entry

Neither `a` nor `b` appears on the per-entry `decoded` records — the
pair lives only inside `wythoff_witness`. Downstream signers that
pinned the entry shape at the nine documented keys stay undisturbed.
