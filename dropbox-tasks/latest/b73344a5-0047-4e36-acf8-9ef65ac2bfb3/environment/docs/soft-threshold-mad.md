# Soft threshold and MAD estimator

## Threshold policy supersession

Policies live as JSON files under the threshold-policies directory. Each file carries `revision_id` (integer), `effective_at` (ISO-8601 UTC string), `case_id`, and `mad_multiplier` (positive float).

Among policies whose `case_id` matches `denoise-config.json` `case_id`, select the active policy as:

1. greatest `effective_at` lexicographically as ISO-8601 UTC
2. if tied, greatest `revision_id`

The active `mad_multiplier` and winning `revision_id` must be frozen into the trace snapshot and threshold journal. Older revisions must not win when a newer effective timestamp exists.

## MAD noise scale

Estimate noise scale from finest detail bands only. Concatenate absolute values from every trace's `D1` band into one pool, then:

sigma = median(|pool|) / 0.6745

Do not include approximation coefficients or coarser detail bands in the MAD sample set. If the pool is empty, sigma = 0.

## Level-dependent soft threshold

Let `N` be the original sample count and `L` the effective level count. The universal base is:

`lambda0 = mad_multiplier * sigma * sqrt(2 * ln(max(N, 2)))`

For detail band `Dj` where `j = 1` is finest and `j = L` is coarsest detail:

`lambda_j = lambda0 / 2^((j - 1) / 2)`

Soft threshold each detail coefficient `c`:

`soft(c, lambda) = sign(c) * max(|c| - lambda, 0)`

with `sign(0) = 0`.

Hard keep (retain the full coefficient when `|c| > lambda`) is not soft thresholding and must not be used for published products. Coefficients just above a level lambda must shrink by exactly that lambda while preserving sign.

## Approximation rule

The coarsest approximation vector `AL` must never be soft-thresholded. Only detail bands `D1 ... DL` receive soft thresholds.
