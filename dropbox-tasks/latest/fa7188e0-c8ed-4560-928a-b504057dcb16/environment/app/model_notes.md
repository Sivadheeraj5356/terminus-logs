# Transport model notes

This is our shallow-aquifer solute model. It tracks the dissolved concentration
`C(x, y, t)` of a contaminant on a rectangular, cell-centred grid. Cell `(i, j)`
is centred at `x = (i - 0.5)*dx`, `y = (j - 0.5)*dy`, with `dx = Lx/nx`,
`dy = Ly/ny`. All quantities are in consistent units (metres, days).

## Physics

Groundwater seeps through the aquifer at a constant seepage velocity
`v = (vx, vy)`. The solute is advected with the flow, spread by hydrodynamic
dispersion, removed by first-order attenuation at rate `lambda`, and continuously
added at the release cell (nearest cell to the source location), which is held at
`source_conc`.

**Dispersion.** Hydrodynamic dispersion is anisotropic and oriented to the flow:
spreading along the direction of flow is set by the longitudinal dispersivity
`alphaL`, and spreading across the flow by the transverse dispersivity `alphaT`,
with molecular diffusion `Dm` on top. Because `alphaL` and `alphaT` act along and
across the flow direction (not along the grid axes), the dispersion is a tensor
aligned with the flow.

**Retardation.** The contaminant sorbs onto the aquifer solids, which slows its
transport relative to the water. The sorption is described by the bulk density
`rho_b`, the distribution coefficient `Kd`, and the porosity `theta`.

## Numerics

Integrate to `end_time` on the grid above. A stable explicit finite-difference
scheme with `nsteps` uniform steps of `dt = end_time/nsteps` is expected. Use
upwind advection, flow-oriented anisotropic dispersion, retardation, first-order
attenuation, a release cell held at `source_conc`, and zero-gradient boundaries.
Keep the final simulation bounded and nonnegative: no final-grid value should be
negative or exceed `source_conc` beyond rounding noise. Monte Carlo samples that
are too fast or dispersive to integrate stably may go non-finite; the driver
discards those samples.

## Reading a well

A monitoring well sits at an arbitrary `(x, y)`, generally not on a cell centre.
Report every baseline and Monte Carlo well concentration from the corresponding
final simulation grid by **bilinear interpolation** of the four surrounding
cell-centre values, not the nearest cell.

## Baseline vs. uncertainty study

The baseline uses the mean parameters directly. The Monte Carlo study draws
`vx, vy, alphaL, alphaT, lambda` per sample from the configured means (spread set
by `cov`), keeping every draw physically valid, and must be reproducible for the
configured seed. Treat `cov` as the coefficient of variation; when `cov` is zero,
every Monte Carlo draw should equal the corresponding configured mean.

## Outputs

Running the driver writes three files under `/app/output`:

- `baseline_final.csv` - the baseline concentration grid, `ny` rows by `nx`
  columns, comma-separated.
- `well_exceedance_probabilities.csv` - header `well_id,x,y,exceedance_probability`,
  one row per configured well; `x` and `y` must match the configured well
  coordinates, and the probability is the fraction of non-discarded Monte Carlo
  samples whose final-grid well reading exceeds `exceedance_threshold`.
- `risk_summary.json` - an object with `seed` equal to the configured seed,
  `n_samples` equal to the configured sample count, `n_discarded`,
  `exceedance_threshold` equal to the configured threshold, `baseline_wells`
  (list of `{id, value}` from the baseline final grid), and `wells` (list of
  `{id, p05, p50, p95}` from non-discarded Monte Carlo final-grid readings).
