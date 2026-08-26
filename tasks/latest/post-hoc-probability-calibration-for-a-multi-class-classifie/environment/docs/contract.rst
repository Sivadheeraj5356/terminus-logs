# Calibration contract

This page is the normative specification for post-hoc confidence calibration
and expected calibration error under distribution shift. Every rule is exact
integer arithmetic. No stage uses floating point, and no stage rounds except
where this page says it rounds. Two implementations that follow this page agree
on every value bit for bit.

Throughout, `unit` and `bins` (written `m`), `cells`, and `lanes` are the
bundle's top-level fields.

## 1. Rounding

`round(num, den)` for `den > 0` is round-half-up:

```
round(num, den) = (2*num + den) / (2*den)      // integer division, truncating
```

`round(7, 2) = 4`. `round(5, 2) = 3`. `round(4, 2) = 2`.

This is the only rounding rule. It is used wherever a mapped value is produced
from a ratio of counts.

## 2. Families

There are three families. Each is fitted on the **fit fold only** (`fit`), never
on a rung's rows. Each maps a `(raw, lane)` pair to an integer value in
`[0, unit]`.

Each family has a fixed **strength**:

| strength | name   | family |
|----------|--------|--------|
| 0        | `hist` | uniform-width histogram |
| 1        | `iso`  | isotonic, pool-adjacent-violators |
| 2        | `giso` | grouped isotonic, pool-adjacent-violators per lane |

Strength orders the families. It is not a claim that a stronger family is always
better on a rung.

### 2.1 `hist` — uniform-width histogram

The cell of a raw score is

```
cell(raw) = raw * cells / (unit + 1)          // integer division
```

clamped into `[0, cells-1]`. Fit fold rows are bucketed by `cell(raw)`. For cell
`k`, let `h` be the number of fit rows in the cell with `hit == 1` and `t` the
number of fit rows in the cell. The cell's value is

```
value(k) = round(unit * h, t)                 if t > 0
value(k) = round(unit * (2*k + 1), 2 * cells) if t == 0        // cell midpoint
```

`hist` maps `raw` to `value(cell(raw))`. It ignores `lane`.

### 2.2 `iso` — isotonic via pool-adjacent-violators

Group the fit fold by **distinct** `raw` value. Rows that share a `raw` value are
one group before any pooling: for a distinct value `v`, `h` is the number of fit
rows with `raw == v` and `hit == 1`, and `t` is the number of fit rows with
`raw == v`.

Walk the distinct values in ascending order maintaining a stack of blocks. A
block is `(lo, h, t)` where `lo` is the smallest raw value it covers. For each
distinct value, form the block `(v, h, t)` and then, while the stack is
non-empty and the current block's ratio is **strictly below** the top block's
ratio, merge the top block into the current block:

```
merge while:  cur.h * top.t  <  top.h * cur.t          // exact, no rounding
on merge:     cur.lo = top.lo ; cur.h += top.h ; cur.t += top.t ; pop
```

Then push the current block. The comparison is a cross-multiplication, so no
rounding takes part in the merge decision. Equal ratios do not merge.

The resulting blocks have `lo` ascending and ratios non-decreasing. To map a
`raw` score, select the **last** block whose `lo` is less than or equal to
`raw`; if `raw` is below the first block's `lo`, select the first block. The
block's value is

```
value = round(unit * block.h, block.t)
```

`iso` ignores `lane`.

### 2.3 `giso` — grouped isotonic

For each lane `g` in `[0, lanes)`, take only the fit rows with `lane == g` and
run the section 2.2 procedure on them, producing one block list per lane.

To map `(raw, lane)`, use lane `lane`'s block list. If lane `lane` has **no** fit
rows, fall back to the `iso` block list of section 2.2.

## 3. Edges

Edges are drawn from the **fit fold concatenated with the rim**, never from a
rung. Maps are still fitted on the fit fold alone (this page, section 2).
Rim rows take part only in edge placement: each rim row is mapped through the
already-fitted family, then the mapped fit values and mapped rim values are
pooled into one ascending list before equal-mass edges are taken.

For family `f`, map every fit fold row and every rim row through `f`, sort the
resulting values ascending into `vals` of length `n`, and take `m - 1` edges:

```
edge[j] = vals[ j * n / m ]        for j = 1 .. m-1        // integer division
```

with the index clamped into `[0, n-1]`. Edges are ascending and may repeat.

Using a rung's own rows to place edges is not this rule. Using the fit fold
alone when the rim is non-empty is not this rule either: sealed edges must
reflect fit and rim together. The durable store under
`/app/environment/docs/protocol.rst` is the authoritative home for those edges
during measurement, selection, and emission.


## 4. Bin assignment

A value `c` falls in the bin

```
bin(c) = the number of edges that are less than or equal to c
```

so `bin(c)` is in `[0, m-1]`.

## 5. Deviation

The deviation of family `f` over a rung's rows uses family `f`'s sealed edges
from section 3 (fit fold concatenated with the rim). For each row, map it
through `f` to a value `c` and place it in `bin(c)`. For each bin `b`,
accumulate over the rows that landed in it:

- `n_b` — how many rows landed in bin `b`
- `h_b` — how many of those rows have `hit == 1`
- `s_b` — the sum of their mapped values `c`

The deviation is

```
deviation = SUM over bins with n_b > 0 of  | unit * h_b  -  s_b |
```

Bins with no rows contribute nothing. The result is an exact non-negative
integer. It is `N` times the mean calibration gap in `unit` scale, where `N` is
the rung's row count, so no division is needed and none is performed.

## 6. Allowance and the budget comparison

For a rung with `N` rows and integer `budget`:

```
allowance = budget * N
```

Family `f` is **within budget** on that rung when

```
deviation(f, rung)  <=  allowance
```

The comparison is between two exact integers. It is `<=`, not `<`.

## 7. Strength span

Each rung carries an integer `span` in `{0, 1, 2}`. When the field is omitted,
`span` is `2`. On the first rung, `span` is ignored. On every later rung, if the
previous chosen strength is `p` and the current chosen strength is `s`, then

```
0 <= s - p <= span
```

Together with section 8 item 4, strengths are non-decreasing and may not jump
upward by more than that rung's `span`.

## 8. What a conforming document must satisfy

A document for a bundle is accepted when all of the following hold.

1. **One family per rung.** Every rung gets exactly one family.
2. **Within budget.** For every rung, the chosen family's deviation over that
   rung, computed by sections 2 through 5 with sealed fit-plus-rim edges, is at
   most that rung's allowance.
3. **Values follow the fit fold map.** For every rung and every row, in the
   bundle's row order, the emitted value equals the chosen family's fit fold map
   applied to that row's `(raw, lane)`.
4. **Strength never decreases.** Reading the ladder in ascending `severity`, the
   chosen strengths are non-decreasing.
5. **Span limits.** Consecutive strengths also obey section 7.
6. **Holdout witness.** The document's top-level `hold` object reports, for every
   family name, that family's deviation on the bundle's `hold` rows using that
   family's sealed fit-plus-rim edges (sections 3 through 5). Keys are `hist`,
   `iso`, and `giso` in that order in the encoding.

Any assignment satisfying items 1 through 5 is accepted. There is no preferred
assignment, no preferred family, and no tie-break rule to reproduce. When more
than one assignment qualifies, emitting any of them passes. The holdout witness
is required on every accepted document and does not change which assignments are
feasible.

## 9. Infeasible ladders

A bundle is infeasible when no assignment satisfies section 8 items 1 through 5.
Infeasibility is a property of the bundle, not an error: a ladder can be
well-formed and still have no ordered assignment that stays within every budget
and span limit.

On an infeasible bundle, `plangen plan`:

- removes the destination path if it exists, so no stale document survives
- writes no document
- exits non-zero

## 10. Determinism and immutability

- Two runs of the same bundle produce byte-identical documents.
- No run writes to the bundle path or to anything under
  `/app/environment/data/`.
- The document is a function of the bundle alone.
- Durable fit-store and journal rules are in
  `/app/environment/docs/protocol.rst`. They do not change the arithmetic on
  this page; they constrain which sealed edges and resume floors a run may use.
