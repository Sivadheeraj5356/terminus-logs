# bracket.md — golden-ratio bracketing helper

`crate::bracket::golden_bracket` is the single-point-of-truth for the
`(phi_p, phi_q)` pair emitted per entry in `results.json`. Split out of
`main.rs` by the 2026-07-09 addendum so the driver never inlines the
`(F_{max_k+1}, F_{max_k})` fibonacci lookups.

## Recipe

Given a sorted-ascending Zeckendorf index list `indices` (as produced by
`crate::zeckendorf::zeckendorf_indices`):

- If `indices` is empty (i.e. `n_effective == 0` — bad-magic or
  unknown-variant fixtures), return `(0, 0)`.
- Otherwise let `max_k` be the greatest element of `indices`. Return
  `(phi_p, phi_q) = (F_{max_k + 1}, F_{max_k})`.

Both `F_{max_k + 1}` and `F_{max_k}` MUST come from
`crate::fibonacci::fibonacci` — no inline Fibonacci table, no
`fibonacci(max_k + 1)` that then recomputes `F_{max_k}` from scratch. A
module that inlines `[1, 2, 3, 5, 8, ...]` is a contract violation.

## Cross-module discipline

`bracket.rs` MUST use `crate::fibonacci`. `main.rs` MUST call
`crate::bracket::golden_bracket` for `phi_p`/`phi_q` — the inline
`(fibonacci(max_k + 1), fibonacci(max_k))` pattern that the pre-split
monolith carried is now a contract violation.

## Ordering invariant

`phi_p >= phi_q` always. On the current corpus every non-zero-`n`
fixture satisfies `phi_p > phi_q` strictly; the equality case
`phi_p == phi_q == 0` occurs only on the `variant == "unknown"` and
bad-magic fixtures per `contracts/rejections.md §VariantUnknown`.

## Not per-entry

The `(phi_p, phi_q)` pair IS emitted per entry as documented on the
main entry shape. `bracket.rs` is the derivation surface — the pair
lands on each `EntryOut.{phi_p, phi_q}` field via `main.rs`. There is
no separate `bracket_witness` proof plane; the pair contributes to
each entry's canonical-JSON SHA (which participates in `chain_sha256`).
