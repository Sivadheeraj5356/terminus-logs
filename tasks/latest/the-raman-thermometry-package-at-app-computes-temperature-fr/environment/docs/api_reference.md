# API Reference — Raman Thermometry

## Configuration

### calibration.toml

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| laser_wavenumber | float | 15798.0 | HeNe laser wavenumber (cm⁻¹) |
| raman_shift_cal | float | 520.0 | Reference Raman shift (cm⁻¹) |
| peak_window_half | float | 15.0 | Peak detection window half-width (cm⁻¹) |
| min_peak_height | float | 10.0 | Minimum peak intensity threshold |
| bose_model | string | "approx" | Bose factor: "approx" (exp approx) or "exact" |
| frequency_exponent | float | 4.0 | ν⁴ pre-factor power law exponent |
| temperature_offset | float | 5.0 | Systematic temperature correction (K) |
| ratio_convention | string | "stokes_over_anti" | Ratio order |

## Report Fields

### Parameters

- `laser_wavenumber` — laser excitation wavenumber (cm⁻¹)
- `raman_shift_cm` — calibrated Raman shift of reference mode (cm⁻¹)
- `bose_model` — Bose population model used
- `frequency_exponent` — exponent used for frequency pre-factor
- `temperature_offset` — calibration offset applied (K)

### Summary

- `stokes_peak_center` — detected Stokes peak position (cm⁻¹)
- `anti_stokes_peak_center` — detected anti-Stokes peak position (cm⁻¹)
- `peak_shift` — half-difference between Stokes and anti-Stokes centers (cm⁻¹)
- `stokes_intensity` — Stokes peak height (arb. units)
- `anti_stokes_intensity` — anti-Stokes peak height (arb. units)
- `stokes_anti_stokes_ratio` — intensity ratio (dimensionless)
- `temperature_estimate` — derived temperature (K)
- `residual` — ratio minus expected reference ratio
