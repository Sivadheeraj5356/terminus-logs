# Spectral processing rules

These rules apply after a dense sample timeline is available. For schema-version 2 that timeline is the pack `samples` array. For schema-version 3 it is the calibrated reconstruction from `/app/docs/pack-v3.md`.

## Framing

Let `N = frame_len` and `sample_count` be the dense timeline length.

Frame starts are `0, hop_len, 2*hop_len, ...` while `start + frame_len <= sample_count`. Partial tails are ignored.

`valid_sample_count` counts numeric non-null timeline samples after calibration.

## Gap policy

For `gap_policy = "skip_frame"`, any candidate frame containing at least one `null` is dropped before quality checks, detrending, or windowing. Those frames increment `dropped_frame_count`.

For `gap_policy = "zero_fill"`, frames containing nulls remain candidates.

## Frame quality (schema-version 3)

For each remaining candidate frame:

```
frame_quality = numeric_sample_count_in_frame / frame_len
```

If `frame_quality < min_frame_quality`, reject the frame. Rejected frames increment `rejected_frame_count` and are not windowed.

Schema-version 2 packs do not carry `min_frame_quality`. Treat them as if every candidate that survives the gap policy is retained (`rejected_frame_count` is omitted from schema-version 2 reports).

`frame_count` counts only retained frames that pass both gap and quality rules.

If no frame is retained, every band reports `energy = 0.0`, `peak_bin = -1`, and `peak_hz = 0.0`.

## Detrending

For `detrend = "none"`, numeric samples are used as-is. Under `zero_fill`, nulls become `0.0`.

For `detrend = "mean"`, compute the arithmetic mean over numeric samples in the frame before null substitution. Subtract that mean from numeric samples. Nulls become `0.0` afterward under `zero_fill`.

If a retained frame has no numeric samples, use mean `0.0`.

## Hann window

Symmetric Hann coefficients for length `N`:

```
w[i] = 0.5 * (1 - cos(2π i / (N - 1)))     when N > 1
w[0] = 1.0                                   when N == 1
```

Windowed sample: `x'[i] = frame_value[i] * w[i]`.

```
window_energy = Σ w[i]²
```

Reported `window_energy` depends only on `frame_len`.

## Bin selection

For each band, candidate bins are `k = 0 ... floor(N / 2)`.

```
f_k = k * sample_rate_hz / N
```

Keep bin `k` when `low_hz <= f_k < high_hz`.

Empty selection yields `bin_count = 0`, `peak_bin = -1`, `peak_hz = 0.0`, `energy = 0.0`.

## Goertzel

For every retained frame and selected bin `k`:

```
ω = 2π k / N
c = 2 cos(ω)
```

Recurrence over the windowed frame:

```
s0 = sample + c*s1 - s2
s2 = s1; s1 = s0
```

Then:

```
real = s1 - s2 cos(ω)
imag = s2 sin(ω)
magnitude_sq = real² + imag²
```

## Weighted band energy

Let `W` be the band weight. Schema-version 2 bands use implicit weight `1.0`.

Sum weighted squared magnitudes over retained frames and selected bins:

```
raw = Σ (W * magnitude_sq)
energy = raw / (frame_count * frame_len * frame_len * window_energy)
```

If `frame_count == 0`, `frame_len == 0`, or `window_energy <= 0`, report `energy = 0.0`. Do not divide by `bin_count`.

## Peak bin

Peak selection uses unweighted magnitude sums over retained frames for each selected bin.

`peak_bin` is the bin with the largest summed magnitude. Ties choose the smaller bin index.

```
peak_hz = peak_bin * sample_rate_hz / frame_len
```

No selected bins or no retained frames means `peak_bin = -1` and `peak_hz = 0.0`.
