# Raman Thermometry Architecture

## Overview

The Raman temperature measurement model implements Stokes/anti-Stokes
thermometry using the Boltzmann population ratio. A 632.8 nm HeNe laser
(ν₀ = 15798 cm⁻¹) excites a sample, and the ratio of Stokes to anti-Stokes
scattered intensities yields the local temperature via the Bose-Einstein
population factor.

## Raman Scattering Theory

The Stokes intensity at shift ν̃ is proportional to (ν₀ − ν̃)⁴ and the
Bose population factor n(ν̃,T) + 1, where n is the Bose-Einstein
distribution n = 1/(exp(hcν̃/kT) − 1). The anti-Stokes intensity is
proportional to (ν₀ + ν̃)⁴ · n(ν̃,T).

The intensity ratio is:

    I_S / I_AS = ((ν₀ − ν̃)/(ν₀ + ν̃))⁴ · exp(hcν̃/kT)

For temperatures above ~200 K and shifts below ~1000 cm⁻¹, the
high-temperature approximation n ≈ kT/hcν̃ is valid, giving
exp(hcν̃/kT) ≈ 1 + hcν̃/kT. Per the calibration standard (Long 1977,
§4.2), the model uses the approximate Bose factor n ≈ exp(−hcν̃/kT)
for computational efficiency when `bose_model = "approx"`.

## Peak Detection

Peaks are identified by scanning the spectrum within ±15 cm⁻¹ of the
expected Stokes and anti-Stokes positions (ν₀ ∓ ν̃_cal). The peak center
is taken as the wavenumber of maximum intensity within the window. Peak
width is measured at half maximum, and area is computed by trapezoidal
integration.

## Temperature Estimation

The temperature is inverted from the intensity ratio:

    T = (hcν̃/k) / ln(R · ((ν₀ + ν̃)/(ν₀ − ν̃))⁴)

where R = I_S/I_AS. A calibration offset (default 5 K) is added to
correct for systematic thermocouple bias per the NIST SRM 2241 protocol.

## Reference Mode

The 520 cm⁻¹ Raman shift corresponds to the first-order optical phonon
mode of silicon, which is the NIST SRM 2241 reference standard. The
cross-section exponent follows the ν⁴ law (Long 1977).
