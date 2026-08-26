# negafibonacci.md — signed-integer Zeckendorf variant

The `crate::negafibonacci` module implements Bunder's 1992 signed-integer
Zeckendorf variant. It is NOT invoked from batch mode — the shipping
batch driver ignores this surface. The five module functions back the
one-off `zeckendorf-encode negafib --n <signed_int>` subcommand
described below.

## Convention

The crate uses the shipping `F_2 = 1, F_3 = 2, F_4 = 3, F_5 = 5, …`
convention (see `zeckendorf.md`). Negafibonacci extends this to signed
integers via the standard identity

    F_{-k} = (-1)^{k+1} · |F_k|      for k ≥ 1

with the boundary `|F_1| = 1` taken to equal `fibonacci(2) = 1` under
the crate convention. Concretely:

    F_{-1} = 1        F_{-2} = -1        F_{-3} = 2
    F_{-4} = -3       F_{-5} = 5         F_{-6} = -8
    F_{-7} = 13       F_{-8} = -21       …

Signed values negate on even `k`; magnitudes match `|F_k|` under the
crate convention. `negafib_abs(1)` MUST return `1`, not `fibonacci(1)`
(which would panic — F_1 does not exist under the shipping convention).

## §values — the module surface

Five functions, all `pub`:

- `negafib_abs(k: u32) -> i64` — `|F_{-k}|`. Delegates to
  `crate::fibonacci::fibonacci(k)` for `k ≥ 2`; returns `1` for
  `k = 1`. Panics on `k = 0`.
- `negafib_value(k: u32) -> i64` — signed `F_{-k}`; negative for even
  `k`.
- `negafib_indices(n: i64) -> Vec<u32>` — canonical negafibonacci
  decomposition of `n`. Returns the empty vector for `n = 0`; otherwise
  a strictly-ascending, non-adjacent list of positive indices.
- `negafib_sum(indices: &[u32]) -> i64` — signed sum
  `Σ F_{-indices[i]}`.
- `negafib_is_minimal(indices: &[u32]) -> bool` — returns `true` iff
  the list is strictly ascending AND no two entries are consecutive
  integers.

## §recipe — canonical decomposition

Greedy algorithm; produces canonical form directly, in linear time:

1. If `n == 0` return `vec![]`.
2. Let `k = 1`. While the smallest `k` such that
   `sign(F_{-k}) == sign(n)` AND `|F_{-k}| ≥ |n|` has NOT been reached,
   increment `k`. Emit `k`.
3. Subtract `F_{-k}` from `n`.
4. Recurse until `n == 0`.
5. Normalize: repeatedly collapse any adjacent pair `(j, j+1)` in the
   emission list using the Bunder identity below.

## §identity — Bunder collapse

    F_{-k} + F_{-(k+1)} = F_{-(k-1)}     for k ≥ 2

Adjacent-index collapse yields a strictly-smaller index. Special case
`k = 1`: `F_{-1} + F_{-2} = 1 + (-1) = 0`, so `[1, 2]` collapses to
`[]` (drop both).

## §canonical — form

`negafib_is_minimal` accepts a list iff BOTH hold:

- strictly ascending: `indices[i] < indices[i+1]` for every `i`;
- non-adjacent: `indices[i+1] != indices[i] + 1` for every `i`.

The empty list and singletons are trivially canonical.

## §reconstruct — sum check

`negafib_sum` MUST return the arithmetic sum
`Σ_i (-1)^{indices[i]+1} · |F_{indices[i]}|` with no overflow shortcut.
`negafib_indices(n)` composed with `negafib_sum` MUST be the identity
on the interval `|n| ≤ 10¹⁸`.

## §subcommand — batch driver dispatch

The batch driver recognises one non-batch entrypoint:

    zeckendorf-encode negafib --n <signed_int>

Behaviour, from strictest to loosest:

1. If `|n| > 10^18`, print
   `SumOverflow: |n|=<abs> exceeds negafib magnitude cap 1e18` to
   stderr and exit `4`.
2. Compute `indices = negafib_indices(n)` and `sum = negafib_sum(&indices)`.
3. If `sum != n`, print
   `NonMinimalNegafibonacci: reconstruction=<sum> does not equal input=<n>`
   to stderr and exit `5`.
4. If `!negafib_is_minimal(&indices)`, print
   `NonMinimalNegafibonacci: indices <list> violate non-adjacency` to
   stderr and exit `5`.
5. Otherwise, print a single canonical-JSON line to stdout with keys
   in lex order `{"indices": [...], "is_minimal": true, "n": <n>,
   "reconstructed": <n>}` followed by a newline, and exit `0`.

The subcommand does not touch `/app/config/zeckendorf_policy.json`
(the batch driver still reads it at startup for policy_witness, but
the value is ignored on the negafib branch). No results.json is
written on this branch.

## §exit-codes

- `0` — success, canonical JSON on stdout.
- `4` — `SumOverflow` (input magnitude cap).
- `5` — `NonMinimalNegafibonacci` (reconstruction mismatch or
  non-canonical form).

Batch-mode exit codes 2 (PolicyLoad) and 3 (CodewordLengthCap) still
apply on the batch branch; they do not fire on the negafib subcommand.
