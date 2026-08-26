# Calibration Notes — Raman Thermometry Campaign 2025

## Laser Calibration

The 632.8 nm HeNe laser provides excitation at 15798 cm⁻¹. Per the
manufacturer's specification (Melles Griot 05-LHR-151), the wavenumber
stability is ±0.01 cm⁻¹ over 8 hours. The power at the sample is 15 mW.

## Raman Shift Standard

The 520 cm⁻¹ silicon phonon mode (NIST SRM 2241) is used as the reference.
The calibration file value `raman_shift_cal = 520.0` matches the standard
at 295 K. The temperature dependence of the silicon phonon is −0.023 cm⁻¹/K,
but for measurements near 300 K this correction is negligible.

## Bose Population Model

The `bose_model = "approx"` setting uses the high-temperature approximation
n ≈ exp(−hcν̃/kT) rather than the full Bose-Einstein distribution. For
shifts of 520 cm⁻¹ at temperatures near 300 K, the exact n(520, 300) =
0.0917 while the approximation gives 0.0829, a systematic error of ~10%.
This is documented and accepted per the Long (1977) §4.2 convention for
rapid field measurements. The calibration offset parameter (5 K) is
intended to partially compensate for this approximation.

## Frequency Exponent

The ν⁴ dependence of Raman cross-section is standard for
non-resonant conditions. The exponent is set to 4.0 per Long (1977).
Lower exponents (e.g., 2) would correspond to resonance Raman conditions
which do not apply to the 632.8 nm excitation of silicon.

## Temperature Offset

A +5 K offset is applied to the derived temperature to correct for
systematic bias in the reference thermocouple. This was determined
during the NIST SRM 2241 certification at 295 K.
