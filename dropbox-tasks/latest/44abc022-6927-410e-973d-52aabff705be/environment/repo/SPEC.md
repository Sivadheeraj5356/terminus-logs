# LOWESS smoothing reference

`lowess` computes a locally weighted scatterplot smoothing (LOWESS) of a set of
scattered `(x, y)` observations. For every input abscissa it produces a fitted
ordinate obtained from a locally weighted linear regression over the nearest
neighbours in `x`. The governing standard is the behaviour of
**`statsmodels.nonparametric.smoothers_lowess.lowess`** (Cleveland, W.S. (1979),
"Robust Locally Weighted Regression and Smoothing Scatterplots", *JASA* 74(368):
829-836), evaluated at the input points with `return_sorted=False`. This document
describes the model, its parameters, and the conventions the implementation must
follow so that the fitted values agree with that reference.

## I/O

The program reads one JSON object from standard input:

```json
{"x": [<float>, ...], "y": [<float>, ...], "frac": <float>, "it": <int>, "delta": <float>}
```

`x` and `y` are equal-length vectors of observations. `frac` is in `[0, 1]`,
`it` is a non-negative integer, and `delta` is a non-negative float. The program
writes exactly one line to standard output: a compact JSON array of the fitted
`y`-values, one per input observation, **in the original input order** (the input
need not be sorted by `x`). Numbers are emitted with full double precision.

## Model

Let `n` be the number of observations. The smoother works on the observations
ordered by ascending `x`; the fitted values are mapped back to the input order
on output.

**Neighbourhood.** Each local regression uses a fixed-size window of the `k`
observations nearest (in `x`) to the point being fitted. The exact size is
`k = int(frac * n + 1e-10)`, clamped to lie between `2` and `n`, where `int`
means truncation toward zero. As the fitted point advances left to right, the
window slides right, always keeping the current point as centred as possible
within the window; once the window reaches the right edge of the data it stays
put. The neighbourhood radius is the larger of the distances from the fitted
point to the two ends of its window.

**Local weights.** Within the window each neighbour receives a weight from the
tricube function of its distance to the fitted point, measured in units of the
neighbourhood radius, so nearer neighbours dominate and the weight falls to zero
at the window edge. The weighted points are then fit with a degree-one (linear)
model and the fitted value is read off at the current abscissa. A window that
carries too little usable weight to support a regression falls back to the raw
observed `y` at that point.

**Robustifying iterations (`it`).** After the initial fit, `it` further passes are
performed. Each pass forms residuals `r_j = y_j - fitted_j`, computes
`m = median(abs(r_j))`, and derives robustness weights with the statsmodels
bisquare convention. If `m > 0`, use `u_j = abs(r_j) / (6 * m)`; if `m == 0`,
use `u_j = 1` for nonzero residuals and `u_j = 0` for zero residuals. Clamp
`u_j` to at most `1`, then set the robustness weight to `(1 - u_j^2)^2` and
fold it into the local tricube weights on the next pass. This progressively
discounts observations with large residuals; `it = 0` performs only the initial
fit. The default in the reference is `it = 3`.

**Interpolation skipping (`delta`).** When `delta > 0`, the regression is not run
at every point. After fitting at a point, all subsequent points lying within
`delta` (in `x`) of it are skipped. The next regression anchor is the last
observation whose `x` is still no greater than the previous fitted `x + delta`
(or the immediately following observation if there is no interior point), and
the skipped points in between are filled by linear interpolation between the two
computed fits. Points sharing an `x` value with the last fitted point copy its
fitted value directly. `delta = 0` (the reference default here) fits every point
and performs no interpolation. `delta` is a speed/accuracy tradeoff for large
data and does not otherwise change the model.

## Parameters

| Field   | Meaning                                                   | Default |
| ------- | --------------------------------------------------------- | ------- |
| `frac`  | Fraction of the data used in each local regression        | 2/3     |
| `it`    | Number of robustifying iterations after the initial fit   | 3       |
| `delta` | Interpolation-skip distance in `x` units                  | 0       |

## Worked example

For `x = [1,2,3,4,5,6,7,8,9,10]`,
`y = [1.0,2.1,1.3,3.6,2.3,4.9,4.1,6.2,5.5,7.8]`, `frac = 0.5`, `delta = 0`:

- with `it = 0` the fitted values are approximately
  `[1.133105, 1.609747, 2.187563, 2.569282, 3.416611, 3.926544, 4.930301, 5.398331, 6.411585, 7.398730]`;
- with `it = 2` they are approximately
  `[1.135918, 1.613420, 2.191472, 2.568201, 3.426394, 3.927673, 4.927313, 5.401772, 6.422485, 7.415238]`.

Values are shown rounded; the program should emit full precision.
