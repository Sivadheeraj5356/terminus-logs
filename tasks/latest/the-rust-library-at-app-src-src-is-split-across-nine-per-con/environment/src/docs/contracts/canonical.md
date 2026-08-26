# canonical.md — canonical-form invariants for Zeckendorf output

Authoritative for the ordering and non-consecutive rules the
`zeckendorf_indices` return value MUST satisfy. Splits off from
`decomposition.md`, which owns the greedy algorithm and the Fibonacci
convention.

## Ascending index order

`zeckendorf_indices(n_effective)` MUST return the index list
**sorted ascending** — smallest index first. This is the shipping
ordering required by `fibonacci_code` (bit position `k - 2` for each
`k`; the terminating `'1'` sits at position `max_k - 1`). Most
textbooks present the decomposition descending; a decoder that emits
descending trips the sorted-ascending invariant asserted per entry
by `test_zeckendorf_indices_sorted_ascending` and the per-entry
canonical-JSON SHA.

## Non-consecutive invariant

No two returned indices differ by 1. That is Zeckendorf's core
uniqueness property — for every non-negative integer `n` there is
**exactly one** index set `S ⊆ {2, 3, 4, ...}` with
`sum(F_k for k in S) == n` and `all(k_{j+1} - k_j >= 2 for j)`. The
top-down greedy in `decomposition.md` naturally preserves this
invariant; a bottom-up sweep that accumulates `F_2, F_3, …` does not
and routinely produces consecutive indices on multi-summand `n`.

The non-consecutive invariant is a property the correct algorithm has
to **preserve**, not a check you can skip on the assumption the
algorithm gets it right. `test_zeckendorf_indices_non_consecutive`
asserts it per entry.

## Empty case pinning

For `n_effective == 0`:

- `zeckendorf_indices(0) == []`
- `zeckendorf_sum([]) == 0`
- `fibonacci_code([]) == ""`
- `phi_p == 0`, `phi_q == 0`

Every zero-`n` fixture (bad-magic + unknown-variant) inherits the
empty-list shape. The Elias-gamma companion is the sole exception —
it pins `n = 0` to `"0"` per `prefix_code.md §Elias gamma`, not the
empty string.

## Ordering under variant reversal

The `zeckendorf` index list itself is variant-independent — the
canonical-form invariants above apply to the raw index set, before the
Fibonacci codeword is materialised. `Variant::ReverseMsb` reverses the
resulting codeword end-for-end (see `variants.md`) but does NOT
re-order the index list; both `canonical` and `reverse-msb` entries
carry the same ascending `zeckendorf` array.

## Uniqueness under `zeckendorf_sum`

The identity `zeckendorf_sum(zeckendorf_indices(n)) == n` holds for
every `n`. Together with the non-consecutive invariant it also implies
`zeckendorf_indices(zeckendorf_sum(idx)) == idx` for every idx that
satisfies the invariants. The round-trip identity is exercised
end-to-end by the `roundtrip_witness` plane; see `roundtrip.md`.
