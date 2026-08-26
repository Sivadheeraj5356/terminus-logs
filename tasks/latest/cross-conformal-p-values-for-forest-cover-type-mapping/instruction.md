# Cross-conformal p-values for forest cover-type mapping

A land-survey program classifies terrain cells into seven forest cover types.
For a batch of unlabelled evaluation cells you must compute, from fixed
nonconformity scores and a K-fold partition of the labelled cells,
**cross-conformal p-values** for every candidate cover type, combine them
across folds with the requested validity-preserving rule, and assemble label
sets — implementing the exact finite-sample procedure below. All graded
arithmetic is exact rational arithmetic; every reported number is a reduced
fraction.

Write a base-R program at `/app/environment/analysis.R`. It reads its input
directory from the environment variable `CONFORMAL_DATA_DIR` (default
`/app/environment/data`) and writes outputs to `CONFORMAL_OUT_DIR` (default
`/app/environment/outputs`). It runs on several input directories with the
same schema but different data (different fold counts included), so implement
the procedure in general. Do not fit any model; the scores are fixed inputs.

## Inputs

- `terrain_cells.csv` — `cell_id, wilderness_area`: every cell.
- `cover_labels.csv` — `cell_id, cover_class` (integer 1–7): labelled cells
  only.
- `fold_registry.csv` — `cell_id, fold`: fold membership of labelled cells.
- `fold_scores_calibration.csv` — `cell_id, fold, score_q`: for each labelled
  cell, its own-label nonconformity score under each listed fold's scoring
  context. **A labelled cell's calibration score for fold `k` is the row with
  its `cell_id` and `fold = k`.** Scores are opaque integers; larger means
  less conforming.
- `fold_scores_evaluation.csv` — `cell_id, fold, class_id, score_q,
  theta_num, theta_den`: for each evaluation cell, fold, and candidate class,
  the fixed evaluation score and the exact smoothing weight
  `theta = theta_num / theta_den` (0 ≤ theta ≤ 1).
- `decision_grid.csv` — `request_id, cell_id, alpha_num, alpha_den,
  combination_rule`: the requests. `combination_rule` is one of `arith2`,
  `bonf`, `median2`.

The **fold universe** is the set of distinct `fold` values appearing in
`fold_scores_evaluation.csv`; `K` is its size. The calibration members of
fold `k` are the labelled cells assigned to `k` by `fold_registry.csv`.

## Procedure

For an evaluation cell `x`, candidate class `y`, and fold `k`: let `S_k` be
the multiset of calibration scores of fold `k`'s members (from
`fold_scores_calibration.csv`, rows with `fold = k`), `n_k` its size, and `s`
the evaluation score of `(x, k, y)` with smoothing weight `theta`.

1. **Per-fold smoothed p-value.** With `g = #{i in S_k : s_i > s}` and
   `e = #{i in S_k : s_i = s}`:

       p_k(x, y) = (g + theta * (e + 1)) / (n_k + 1)

   A fold with no calibration members (`n_k = 0`, so `g = e = 0`) gives
   `p_k = theta`.

2. **Combination.** Over the `K` per-fold p-values, by the request's rule:
   - `arith2`:  `min(1, 2 * (p_1 + ... + p_K) / K)`
   - `bonf`:    `min(1, K * min_k p_k)`
   - `median2`: `min(1, 2 * median_k p_k)`; for even `K` the median is the
     mean of the two middle order statistics.

3. **Label set.** At the request's level `alpha = alpha_num / alpha_den`, the
   set contains exactly the classes with `p_combined(x, y) > alpha` —
   strictly greater; a combined p-value exactly equal to `alpha` is excluded.

4. **Diagnostics.** For every combination of `wilderness_area`, level, and
   rule that occurs among the requests: the mean set size over those
   requests, as an exact reduced fraction.

## Outputs

Write exactly two CSV files, with exact reduced fractions (`gcd`-reduced,
denominator positive; integers rendered with denominator 1):

- `pvalues.csv` — header `request_id,class_id,p_num,p_den,in_set`; one row
  per request and class (`class_id` 1–7), ordered by `request_id` then
  `class_id`. `p_num/p_den` is the combined p-value; `in_set` is 1 or 0.
- `diagnostics.csv` — header
  `wilderness_area,alpha_num,alpha_den,combination_rule,mean_setsize_num,mean_setsize_den`;
  one row per occurring (area, level, rule) combination, ordered by
  `wilderness_area`, then `alpha_num/alpha_den` ascending, then rule
  alphabetically. Levels are reported exactly as given in the grid.

Every quantity above is exactly representable; keep all arithmetic exact
(integer counting and fraction arithmetic — no floating-point comparisons of
p-values against levels). Derive every result from the supplied bundle:
fold counts, fold sizes, score ranges, smoothing weights, levels, and rules
all vary between invocations.
