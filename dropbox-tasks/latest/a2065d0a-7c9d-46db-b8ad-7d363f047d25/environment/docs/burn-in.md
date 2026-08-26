# Burn-in and retained theta accumulation

Sweeps are numbered 1 through `sweeps`. The first `burn_in` completed sweeps are excluded from aggregation. A sweep contributes to aggregation only when its 1-based number is strictly greater than `burn_in`. The number of contributing sweeps is `retained_sweeps = sweeps - burn_in`, and the configuration guarantees `sweeps > burn_in >= 0` so this value is at least one.

Immediately after a contributing sweep completes, add that sweep's per-document topic distribution into the accumulator `theta_sum`. For document `d` with row total `row_total = sum_k n_dk[d][k]`:

    theta_sum[d][k] += (n_dk[d][k] + alpha) / (row_total + K * alpha)

for every topic `k`, using the counts as they stand at the end of that sweep. A non-contributing (burn-in) sweep must not modify `theta_sum`.

`theta_sum` and `retained_sweeps` are both stored in the count staging snapshot. The exported per-document distribution divides `theta_sum` by `retained_sweeps` (see `rollup-export.md`). Including a burn-in sweep in the accumulation, or dividing by the wrong number of sweeps, changes the exported distribution.
