# Troubleshooting — Raman Thermometry

## Temperature Estimates Are Too High

If the reported temperature exceeds the expected value by more than 10 K,
the Stokes/anti-Stokes ratio may be overestimated. Verify that the peak
detection window correctly captures the full peak profile. If the
anti-Stokes peak is too weak (below `min_peak_height`), the ratio becomes
ill-defined and the temperature defaults to the calibration offset.

The `bose_model = "approx"` setting intentionally underestimates the Bose
factor at low temperatures, which can produce an overestimated temperature.
If running below 250 K, consider switching to `bose_model = "exact"`.

## Ratio Is Near Zero

A near-zero ratio typically indicates the anti-Stokes peak is not detected.
Check the `min_peak_height` parameter — raising it may help filter noise
but can also reject real weak peaks at low temperatures.

## Peak Shift Does Not Match Calibration

If the reported peak shift differs from the `raman_shift_cal` value,
the peak detection algorithm may be picking up a different spectral
feature. The default window ±15 cm⁻¹ should capture the full silicon
phonon line. If the spectrum was acquired with a different laser
wavelength, update `laser_wavenumber` in the calibration file.

## Negative Temperature Estimates

A negative temperature indicates the anti-Stokes intensity exceeds the
Stokes intensity, which is unphysical for spontaneous Raman scattering.
This can occur if the ratio convention is inverted. Set
`ratio_convention = "stokes_over_anti"` if `anti_over_stokes` was
inadvertently selected.
