`/app` holds a small C program named `lowess` that fits a locally weighted
scatterplot smoothing (LOWESS) curve to scattered `(x, y)` data. The
standard-input decoding and the standard-output formatting in `/app/lowess.c` are
already wired up and working; what is missing is the numerical core, the
`lowess_fit` function, which right now just echoes the raw `y`-values back so the
program runs without actually smoothing anything. Your job is to implement it so
the fitted values match the governing standard. Keep the implementation in
`/app/lowess.c` as source-based C that can be rebuilt into the `lowess`
executable with a standard C compiler and `libm`; use no external dependencies
and no network access.

The program reads a single JSON object from standard input of the shape
`{"x":[...],"y":[...],"frac":<float>,"it":<int>,"delta":<float>}` and writes
exactly one line to standard output: a compact JSON array of the smoothed
`y`-values fitted at each input `x`, given in the original input order and printed
with full double precision. `frac` is the fraction of the data used in each local
regression, `it` is the number of robustifying iterations, and `delta` is the
interpolation-skip distance.

Treat `statsmodels.nonparametric.smoothers_lowess.lowess`, evaluated at the input
points, as the governing standard for how the smoother behaves: how the
neighbourhood of each point is chosen, how the tricube neighbour weights and the
local linear fit are formed, how the robustifying iterations reweight residuals,
how `delta` interpolation is applied, and how the boundary and degenerate cases
are resolved. The model, its parameters, its conventions, and a worked example are
documented in `/app/SPEC.md`. Keep the command surface and the `lowess_fit`
entry point intact.
