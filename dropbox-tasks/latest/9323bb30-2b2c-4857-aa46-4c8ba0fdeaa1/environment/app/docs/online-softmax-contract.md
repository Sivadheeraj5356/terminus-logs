# Online softmax contract

Per-head online softmax over attention tensor logits (FlashAttention-style tile reductions). Per head, maintain running statistics `(m, ell)` initialized to `m = -inf`, `ell = 0`.

**Visit filter (axiom):** walk the full tile visitation order from tile-schedule-contract.md. Apply a softmax update for head `h` only when the pair `(qi, kj)` is a **mask-kept** pair from sparse-mask rehydration. Do not undercount by collapsing to unique `kj` per head, and do not overcount by updating on non-kept pairs. Each kept `(qi, kj)` still updates **every** head independently (one update per head per kept pair).

When a tile contributes local max `m_tile` and local sum-exp `ell_tile`:

1. `m_new = max(m, m_tile)` (IEEE-754; treat `-inf` as less than any finite)
2. `alpha = exp(m - m_new)` when `m` is finite; else `alpha = 0` if `m` was `-inf` and `m_new` is finite; else `alpha = 1` if both `-inf`
3. `ell = ell * alpha + ell_tile * exp(m_tile - m_new)`
4. Any accumulator `O_acc` must be multiplied by the same `alpha` before adding the tile contribution

`m_stats` in the seal is the list of final `m` values per head in head order, encoded as decimal strings with exactly 6 fractional digits (round half away from zero).
`ell_stats` is the list of final `ell` values per head with the same decimal encoding.
