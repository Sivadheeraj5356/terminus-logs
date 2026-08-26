# Statistics Specification

## SLA Met Percentage

```
sla_met_pct = (count of resolutions where sla_met = 1) / (total count of resolutions) * 100
```

- Formatted to 4 decimal places (e.g., `100.0000`, `0.0000`, `66.6667`).
- If there are no resolutions, output `0.0000`.

## Nearest-Rank Percentile

Used for p50, p75, and p95 of `resolution_minutes`.

```
rank = ceil(q * n)   // 1-indexed
value = sorted[rank - 1]
```

Where:
- `q` is the quantile (0.50, 0.75, 0.95)
- `n` is the total number of resolutions
- `sorted` is the array of `resolution_minutes` values sorted ascending
- `rank` is clamped to `[1, n]`

If there are no resolutions, output `0`.

### Examples

n=3, values=[10, 30, 50] (sorted):
- p50: rank = ceil(0.5 * 3) = ceil(1.5) = 2 → value = 30
- p75: rank = ceil(0.75 * 3) = ceil(2.25) = 3 → value = 50
- p95: rank = ceil(0.95 * 3) = ceil(2.85) = 3 → value = 50

## Population Standard Deviation

```
mean = sum(x) / n
variance = sum((x - mean)^2) / n
std = sqrt(variance)
```

- Formatted to 4 decimal places (e.g., `5.0000`).
- If there are no resolutions, output `0.0000`.

### Example

Values = [10, 20]: mean = 15, variance = ((10-15)^2 + (20-15)^2) / 2 = 25, std = 5.0000.

## Median (Nearest-Rank) and Median Absolute Deviation

`median_resolution_minutes` in `dispersion-report` uses the exact same nearest-rank formula as p50/p75/p95 above (`rank = ceil(0.50 * n)`, 1-indexed into the ascending-sorted array) — it is **not** the textbook "average the two middle values when n is even" definition. For even `n` the two definitions diverge.

`mad_resolution_minutes` (median absolute deviation) reapplies that identical nearest-rank formula a second time, to the sorted list of `|x_i - median_resolution_minutes|` deviation values (using the median computed above; since `resolution_minutes` are integers, the nearest-rank median itself is always an exact integer value).

`mad_normalized` = `mad_resolution_minutes * 1.4826` — the standard consistency constant used to make MAD comparable to a normal-distribution standard deviation.

- If there are zero resolutions: `median_resolution_minutes=0`, `mad_resolution_minutes=0.0000`, `mad_normalized=0.0000`.
- If there is exactly one resolution: `median_resolution_minutes` is that single value, and both MAD fields are `0.0000`.

### Example

n=4, values=[10, 20, 30, 40] (sorted):
- median: rank = ceil(0.5 * 4) = 2 → sorted[1] = 20 (NOT the textbook average of 20 and 30, which would be 25)
- deviations: |10-20|=10, |20-20|=0, |30-20|=10, |40-20|=20 → sorted = [0, 10, 10, 20]
- mad: rank = ceil(0.5 * 4) = 2 → sorted[1] = 10 → `mad_resolution_minutes=10.0000`
- mad_normalized = 10 * 1.4826 = `14.8260`
