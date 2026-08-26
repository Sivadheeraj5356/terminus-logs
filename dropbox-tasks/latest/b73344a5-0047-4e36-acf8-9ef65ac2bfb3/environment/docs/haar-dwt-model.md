# Orthonormal Haar DWT model

## Pair transform

For adjacent even/odd samples `(x0, x1)` the orthonormal Haar pair is:

- approximation `a = (x0 + x1) / sqrt(2)`
- detail `d = (x0 - x1) / sqrt(2)`

The inverse pair is:

- `x0 = (a + d) / sqrt(2)`
- `x1 = (a - d) / sqrt(2)`

Unnormalized averages such as `(x0 + x1) / 2` or `(x0 + x1)` are not compliant. The same `1/sqrt(2)` scale must appear on both forward and inverse pairs.

## Multi-level pyramid

Level 1 decomposes the (padded) sample vector into approximation vector `A1` and detail vector `D1`. Subsequent levels decompose only the current approximation. After `L` levels the coefficient layout is `[AL, DL, D(L-1), ..., D1]` with `AL` the coarsest approximation and `D1` the finest detail band.

## Odd-length padding

Before each decomposition level, if the current vector length is odd, append one copy of the last sample (repeat-pad) so the length becomes even. Record the pre-pad length for that level. After the matching inverse step, truncate back to the recorded pre-pad length. Zero-pad or reflection pad are not used.

## Level clamp

Let `n` be the original (unpadded) sample count for a trace. The maximum admissible level count is `L_max = floor(log2(n))` when `n >= 2`, else `0`.

Effective levels:

`L = min(requested_levels, max_levels from denoise-config.json, L_max)`

Never panic, invent empty bands, or decompose past `L_max`. When `L_max = 0`, leave samples unchanged and emit empty detail bands.

## Round-trip without thresholding

With soft thresholds disabled (multiplier treated as zero thresholds), a full forward/inverse pyramid must recover the original samples within floating-point tolerance after padding trim.
