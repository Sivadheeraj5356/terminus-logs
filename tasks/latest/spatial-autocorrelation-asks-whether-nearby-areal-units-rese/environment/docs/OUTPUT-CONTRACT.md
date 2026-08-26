# Output contract

On well-formed input the program prints exactly thirty-four lines, each of the
form `LABEL = ...`. Lines 1-12 are the join-count suite for the first-order
weight matrix `W1`; lines 13-24 are the identical suite recomputed for the
derived second-order weight matrix `W2`, with every label prefixed by `W2_`;
lines 25-31 are the numeric-attribute block (Moran's I and Geary's C of `value`);
lines 32-34 are the exact conditional-permutation p-values of the `W1` join counts.
All arithmetic is exact: counts are integers and every moment is an exact reduced
rational. Do not use floating point.

The two blocks share one colouring. The unit labels, `n`, `n1`, `n0`, and hence
the free/nonfree colour probabilities `m2, m3, m4` (below) are identical for both
blocks. Only the weight matrix (and therefore `S0, S1, S2` and the observed
`BB, WW, BW`) differs between the `W1` block and the `W2` block. The same moment
identities must be re-evaluated against the second matrix; reusing the `W1` weight
sums in the `W2` moment lines is wrong.

## The second-order weight matrix W2

`W2` is the boolean second-order (lag-2) contiguity matrix built from `W1`:

- `W2[i, j] = 1` iff `i != j`, `{i, j}` is NOT a first-order edge (`W1[i, j] = 0`),
  and `i` and `j` have at least one common first-order neighbour (equivalently,
  there is a walk of exactly two steps from `i` to `j` in `W1`).
- `W2[i, j] = 0` otherwise. `W2` is symmetric with a zero diagonal.

Construction is a boolean 2-hop closure with the diagonal and `W1` removed:
take the reachable-in-two-steps relation `(W1 %*% W1 > 0)`, then set the diagonal
to `0` and zero out every entry where `W1` is `1`. The weight is strictly `0/1`:
the number of distinct 2-paths between `i` and `j` is never used as a weight, and
`W2` is not `W1` plus anything. `W2` may be empty (for example a single edge, a
disjoint matching, a triangle, or any complete graph has no second-order
neighbours); an empty `W2` gives `W2_S0 = 0`, zero observed counts, and every
`W2` moment cell `E = 0`, `Var = 0`, label `NA`.

Because `W2` is again a symmetric binary matrix with zero diagonal, all the `W1`
formulas below apply verbatim to `W2` with `W2`'s own edge set and degrees.

## Weight sums (integers)

With a symmetric binary weight matrix `W` (`W1` for the first block, `W2` for the
second; `S0`, `S1`, `S2` are the standard Cliff-Ord weight sums):

- `S0 = sum_i sum_j w_ij`. For symmetric binary weights `S0 = 2M`, where `M` is
  the number of undirected edges of `W`.
- `S1 = (1/2) sum_i sum_j (w_ij + w_ji)^2`. For symmetric binary weights
  `S1 = 2 * S0 = 4M`.
- `S2 = sum_i (sum_j w_ij + sum_j w_ji)^2`. For symmetric binary weights
  `S2 = 4 * sum_i d_i^2`, where `d_i` is the degree of unit `i` in `W`.

Lines 1-3 (and 13-15 with the `W2_` prefix):

```
S0 = <integer>
S1 = <integer>
S2 = <integer>
```

## Observed join counts (integers, half / undirected convention)

Each undirected edge of the weight matrix is counted once. For an edge `{i, j}`:

- `BB` counts edges with both endpoints black (`label 1`).
- `WW` counts edges with both endpoints white (`label 0`).
- `BW` counts edges whose endpoints differ.

By construction `BB + WW + BW = M = S0 / 2`. Lines 4-6 (and 16-18 with `W2_`):

```
BB = <integer>
WW = <integer>
BW = <integer>
```

## Analytical moments under two nulls

Lines 7-12 (and 19-24 with the `W2_` prefix) report, for each of the two null
models and each join type, the exact expectation, exact variance, and a
significance label:

```
FREE_BB = <E> <Var> <label>
FREE_WW = <E> <Var> <label>
FREE_BW = <E> <Var> <label>
NONFREE_BB = <E> <Var> <label>
NONFREE_WW = <E> <Var> <label>
NONFREE_BW = <E> <Var> <label>
```

`<E>` and `<Var>` are exact reduced fractions printed as `numerator/denominator`
with denominator `>= 1` and `gcd(numerator, denominator) = 1`; integers are
printed as `k/1` (for example `181/1`, `2378914209/32132518`).

### Unified moment formulas

For a join type let `(m2, m3, m4)` be three null-dependent pair/triple/quad
colour probabilities defined below. With the weight sums `S0, S1, S2` of the
matrix for the current block,

- `E = (S0 / 2) * m2`
- `Var = (1/4) * ( S1*m2 + (S2 - 2*S1)*m3 + (S0^2 - S2 + S1)*m4 ) - E^2`

The `(m2, m3, m4)` are colouring-only and identical for the `W1` and `W2` blocks.

Free sampling (each unit independently black with probability `p = n1/n`,
`q = 1 - p`):

- BB: `m2 = p^2`, `m3 = p^3`, `m4 = p^4`
- WW: `m2 = q^2`, `m3 = q^3`, `m4 = q^4`
- BW: `m2 = 2pq`, `m3 = pq`, `m4 = 4 p^2 q^2`

Nonfree (conditional / permutation) sampling, with `n1` fixed. Write the falling
factorial `n^(k) = n (n-1) ... (n-k+1)`:

- BB: `m2 = n1^(2)/n^(2)`, `m3 = n1^(3)/n^(3)`, `m4 = n1^(4)/n^(4)`
- WW: `m2 = n0^(2)/n^(2)`, `m3 = n0^(3)/n^(3)`, `m4 = n0^(4)/n^(4)`
- BW: `m2 = 2 n1 n0 / n^(2)`, `m3 = n1 n0 (n - 2) / n^(3)`,
  `m4 = 4 n1^(2) n0^(2) / n^(4)`

When a falling factorial denominator is zero (that is, `n < 2` for the `m2`
term, `n < 3` for the `m3` term, or `n < 4` for the `m4` term) the corresponding
nonfree term is taken to be exactly `0`. In particular a single-unit map has all
nonfree terms zero.

## Significance label

For each cell let `Obs` be the observed count (from the same block's weight
matrix), `E` and `Var` as above, and `dev = Obs - E`. The label uses the
disclosed two-sided cut `|z| > 2`, tested exactly as `dev^2 > 4 * Var`:

- If `Var = 0` the standardized comparison is undefined; the label is the
  sentinel `NA` (this covers the monochromatic / all-one-colour case, an empty
  `W2`, and any other zero-variance cell).
- Else if `dev = 0` the label is `NS`.
- Else if `dev^2 > 4 * Var` (strict) the label is `HIGH` when `dev > 0` and
  `LOW` when `dev < 0`.
- Otherwise the label is `NS`.

## Numeric-attribute block (lines 25-31)

The last seven lines analyse the numeric attribute `value` (call it `z`) for
spatial autocorrelation with Moran's I and Geary's C. Write `zbar = (sum_i z_i)/n`,
the deviations `u_i = z_i - zbar`, `m2 = sum_i u_i^2`, `m4 = sum_i u_i^4`, and the
sample kurtosis `b2 = n * m4 / m2^2`.

```
Z_MEAN = <zbar>
Z_SS = <m2>
MORAN = <I> <E> <Var> <label>
GEARY = <C> <E> <Var> <label>
W2_MORAN = <I> <E> <Var> <label>
W2_GEARY = <C> <E> <Var> <label>
STD_MORAN = <I> <E> <Var> <label>
```

`Z_MEAN` and `Z_SS` are exact reduced fractions. `MORAN`/`GEARY` use the binary
`W1`; `W2_MORAN`/`W2_GEARY` use the binary `W2`; `STD_MORAN` uses the
row-standardized `W1` (below). For a weight matrix `W` with Cliff-Ord sums
`S0, S1, S2` (defined exactly as above, but now for a possibly asymmetric,
possibly rational `W`):

- `I = (n / S0) * ( sum_i sum_j w_ij u_i u_j ) / m2`
- `C = ((n - 1) / (2 * S0)) * ( sum_i sum_j w_ij (z_i - z_j)^2 ) / m2`
- `E[I] = -1 / (n - 1)`, and `E[C] = 1`.
- Randomization variances (Cliff-Ord), valid for `n >= 4`:
  `Var[I] = [ n((n^2-3n+3) S1 - n S2 + 3 S0^2) - b2((n^2-n) S1 - 2n S2 + 6 S0^2) ]
  / [ (n-1)(n-2)(n-3) S0^2 ] - 1/(n-1)^2`, and
  `Var[C] = [ (n-1) S1 (n^2-3n+3 - (n-1) b2) - (1/4)(n-1) S2 (n^2+3n-6 - (n^2-n+2) b2)
  + S0^2 (n^2-3 - (n-1)^2 b2) ] / [ n(n-2)(n-3) S0^2 ]`.

The row-standardized `W1` divides each row by its row sum, so `w_ij = a_ij / d_i`
for a unit `i` of degree `d_i > 0` (an isolated unit keeps an all-zero row).
Then `S0 = ` (number of non-isolated units), and `S1`, `S2` follow the general
asymmetric definitions `S1 = (1/2) sum_i sum_j (w_ij + w_ji)^2`,
`S2 = sum_i (sum_j w_ij + sum_j w_ji)^2`.

`<I>`, `<C>`, `<E>`, `<Var>` are exact reduced fractions `numerator/denominator`.
The `<label>` is the two-sided verdict of the standardized deviate `dev`
(`I - E[I]` for Moran, `C - E[C]` for Geary), tested exactly as `dev^2 > 4 Var`,
with the same `HIGH`/`LOW`/`NS`/`NA` rule as the join-count cells. Degenerate
cases:

- If `m2 = 0` (the attribute is constant) or `S0 = 0` (no edges / empty `W2` /
  every unit isolated), the whole line is `NA NA NA NA`.
- If `2 <= n <= 3`, `I`, `C` and `E` are printed but the randomization variance
  is undefined, so the line is `<value> <E> NA NA`.

## Conditional-permutation p-values (lines 32-34)

The last three lines give the exact two-sided p-value of each observed `W1` join
count under the conditional (nonfree) null, in which the number of black units `n1`
is held fixed and every labelling of the `n` units with exactly `n1` black is equally
likely (there are `C(n, n1)` of them).

```
PVAL_BB = <p or NA>
PVAL_WW = <p or NA>
PVAL_BW = <p or NA>
```

For a join type, let `obs` be its observed count on `W1`, let `X` be its count on a
labelling, and let `mu = E[X]` be the exact conditional mean (the `NONFREE` expectation
of the unprefixed block). The two-sided p-value is the exact reduced fraction

```
p = |{ labellings with |X - mu| >= |obs - mu| }| / C(n, n1),
```

computed by enumerating all `C(n, n1)` labellings; the deviations are compared exactly as
rationals. The value is `NA` in exactly two cases: when `C(n, n1) > 20000` (too many
labellings to enumerate), and when the count is the same on every labelling (zero
permutation variance). The p-values use the first-order matrix `W1` only; there is no
`W2_` p-value.

## Full line order

```
S0, S1, S2, BB, WW, BW,
FREE_BB, FREE_WW, FREE_BW, NONFREE_BB, NONFREE_WW, NONFREE_BW,
W2_S0, W2_S1, W2_S2, W2_BB, W2_WW, W2_BW,
W2_FREE_BB, W2_FREE_WW, W2_FREE_BW, W2_NONFREE_BB, W2_NONFREE_WW, W2_NONFREE_BW,
Z_MEAN, Z_SS, MORAN, GEARY, W2_MORAN, W2_GEARY, STD_MORAN,
PVAL_BB, PVAL_WW, PVAL_BW
```
