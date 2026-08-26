# Lunar regolith thermophysics fixtures

Synthetic offline Diviner-style column inputs for the lunar thermal-inertia
and eclipse inversion study. Read from `--data-dir` (default `/app/data`).
Column meanings, SI units, and governing equations are normative under
`/app/docs/`.

## Files

| File | Role |
|------|------|
| `materials.csv` | Thermophysical material `lunar_regolith` (density, \(c_p(T)\) coefficients, contact + radiative conductivity, albedo, emissivity) |
| `depth_grid.csv` | Six-cell nonuniform columns for each illumination case |
| `illumination_cases.csv` | Forward cases `case_diurnal`, `case_eclipse`, `case_gradient` (period, solar/geothermal flux, conductivity scale, albedo offset, spin-up limits) |
| `forcing_intervals.csv` | Four contiguous forcing intervals per case covering one 3600 s period |
| `eclipse_profiles.csv` | Profiles `none` (transmission 1) and `partial_eclipse` (dip to 0.35 mid-period) |
| `radiometer_bands.csv` | Response samples for `band_8um` and `band_25um` |
| `observation_queries.csv` | Six step-boundary observation requests (noon/dusk × three cases) |
| `inversion_queries.json` | Fits `fit_cond` (conductivity scale) and `fit_two` (conductivity scale + albedo offset) |
| `solver_config.json` | Physical constants, time step, nonlinear / brightness / inversion tolerances, output decimal places |

## Case intent

- `case_diurnal` — ordinary diurnal forcing with profile `none`, unit conductivity scale.
- `case_eclipse` — same solar geometry with `partial_eclipse` transmission.
- `case_gradient` — elevated conductivity scale (1.2) and slightly higher geothermal flux; used by the two-parameter fit.

Grids thicken with depth (0–5 cm, 5–10 cm, then progressively thicker layers to 60 cm). Initial temperatures differ by case (220 K / 215 K / 210 K) to exercise spin-up.

## Notes

- Row order inside CSV files is not authoritative; the solver sorts by the
  semantic keys in `data_contract.md`.
- Observation times (1800 s, 3300 s) align with `time_step_s = 300`.
- No expected report is shipped here; temperatures, radiances, and fits must
  be computed from these inputs and the public contracts.
