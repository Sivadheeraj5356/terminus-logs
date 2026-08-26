# Analysis contract

Every reported quantity is an integer and there is no floating tolerance
anywhere in the graded output. Field values may be negative, zero, or large;
every persistence and every reported total is an exact integer.

## Input data (`/app/data`)

Each structure is a square integer scalar field sampled on an `N` by `N` grid of
vertices.

- `field.csv`: `structure_id, row, col, value`. One row per grid vertex.
  `row` and `col` are 0-based; a structure's side length `N` is one more than the
  largest `row` (equivalently the largest `col`) seen for that structure, and
  every `(row, col)` with `0 <= row, col < N` occurs exactly once. Rows may appear
  in any order; reconstruct `V[row][col]` from them.
- `reference_labels.csv`: `structure_id, fold_group`. The authoritative list of
  reference structures and each one's fold group.
- `queries.csv`: `structure_id`. The authoritative list of structures to label.
- `structures.csv`: `structure_id, role, size`. A convenience summary only. It is
  **not** authoritative and may be incomplete or inconsistent with the other files
  (wrong roles or sizes, missing structures, extra structures that appear nowhere
  else). Never use it to decide which structures are references or queries or how
  large a field is. A structure present in `field.csv` but listed as neither a
  reference nor a query is ignored.

## Complex and filtration

Read `V[row][col]` as a scalar function on the triangulated grid whose simplices
are:

- one vertex per grid point `(r, c)`, carrying value `V[r][c]`;
- one edge for each horizontally adjacent pair `(r, c)`–`(r, c+1)`, each
  vertically adjacent pair `(r, c)`–`(r+1, c)`, and, in every unit square, the
  diagonal `(r, c)`–`(r+1, c+1)`;
- two triangles per unit square, split by that diagonal:
  `{(r, c), (r, c+1), (r+1, c+1)}` and `{(r, c), (r+1, c), (r+1, c+1)}`.

The filtration value of a simplex is the **maximum** of its vertices' values.

## Bar families

Work over the field with two elements. From the filtration above read four
multisets of finite bars, each bar having a birth value, a death value, and an
integer persistence equal to their difference; only bars of strictly positive
persistence are retained.

- `Ord_0`, `Ord_1` — the finite bars in homological dimensions 0 and 1 of the
  sublevel-set persistence, i.e. of the filtration in which each simplex enters at
  its filtration value as a threshold rises. Persistence is `death - birth`.
- `Rel_0`, `Rel_1` — the finite bars in dimensions 0 and 1 of the superlevel-set
  persistence: the same construction applied with the field negated (equivalently,
  each simplex entering at the **minimum** of its vertices' values as a threshold
  falls). Persistence is `birth - death`.

Also define `ext0 = (maximum field value) − (minimum field value)`.

## Significance floor

Let `M` be the largest persistence occurring among the ordinary bars
(`Ord_0` and `Ord_1` taken together), or `0` if there are none, and let
`σ = floor(M / 4)`. When the families are summarized below, a bar contributes only
if its persistence is **strictly greater** than `σ`; every bar with persistence at
most `σ` is discarded first. `ext0` is not subject to the floor.

## Feature vector

Summarize a structure as seventeen integers in this exact order. For each family,
after discarding the bars at or below the floor, let `count` be how many bars
remain, `total` the sum of their persistences, `max` the largest remaining
persistence (`0` if none remain), and `second` the second-largest (`0` if fewer
than two remain).

1–4. `Ord_0`: count, total, max, second.
5–8. `Ord_1`: count, total, max, second.
9–12. `Rel_0`: count, total, max, second.
13–16. `Rel_1`: count, total, max, second.
17. `ext0`.

## Retrieval and labeling

For each query, compute its seventeen-integer feature vector and that of every
reference. The distance between two vectors is their **L1 distance**, the sum of
the absolute differences of the seventeen components. Retrieve the reference with
the smallest distance; break ties by the lexicographically smallest
`structure_id`. The query's predicted fold group is the retrieved reference's
`fold_group`.

## Output

Process queries in ascending `structure_id` order. Print one line per query with
twenty space-separated fields and a trailing newline:

```
<query_id> <retrieved_reference_id> <predicted_fold_group> <f1> <f2> ... <f17>
```

where `<f1> ... <f17>` are the seventeen feature integers above. Print nothing
else. The program takes the data directory as its first argument and defaults to
`/app/data`.
