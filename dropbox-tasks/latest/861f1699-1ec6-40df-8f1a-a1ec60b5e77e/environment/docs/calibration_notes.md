# Lab calibration notes (2023 east-boutique regression)

Microphone placement follows the east-boutique layout. Coordinates and acceptance
thresholds load from `/app/environment/config/lab.toml` (`bridge_x`, `bridge_y`,
`mic_x`, `mic_y`, `formant_min_hz`, `formant_max_hz`, `peak_min_db`,
`peak_min_sep_hz`, `formant_tolerance_hz`, `sample_rate_hz`).

Voxel `0` is air cavity and voxel `1` is wood shell; laboratory wave speeds are
the constants in `/app/environment/include/ac_limits.h`. Bridge excitation uses the
configured bridge cell and early-step drive window documented with the time step
constants in that header. The leapfrog update uses the Courant number derived from
local speed, `AC_DT`, and `AC_DX` as specified in the scientific workflow.

## Peak acceptance

Recovered peaks are local spectral maxima inside `[formant_min_hz, formant_max_hz]`.
Magnitude is absolute decibels `20 * log10(|FFT| + 1e-30)`. Accept only when that
absolute dB is at least `peak_min_db`. Keep four strongest peaks by dB with mutual
separation of at least `peak_min_sep_hz`. `peak_prominence_db` is the strongest
accepted peak absolute dB.

## Regression accuracy

Sorted `formants_hz` must match lab regression targets within `formant_tolerance_hz`
for each shipped CT stem under the full assay (mesh staging bind, leapfrog, and
peak rules). See `/app/docs/lab-closure-calibration-contract.md` and
`/app/docs/cavity-mesh-staging.md`.
