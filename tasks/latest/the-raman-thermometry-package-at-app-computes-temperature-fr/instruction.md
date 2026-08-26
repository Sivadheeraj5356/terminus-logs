The Raman thermometry package at `/app` computes temperature from Stokes/anti-Stokes intensity ratios for sample `raman_calib_2025_001`. The output report at `/app/output/report.json` currently gives physically wrong temperatures — the reported value is inconsistent with the detected peak positions and intensity ratio in the spectrum.

Fix the code so the reported temperature is physically consistent with the measured spectrum. Specifically, the Stokes and anti-Stokes peaks should each be detected as the single highest-intensity point within ±15 cm⁻¹ of their expected positions. The reported Raman shift (`parameters.raman_shift_cm` and `summary.peak_shift`) is the signed value (Stokes wavenumber − anti-Stokes wavenumber)/2, which is negative since Stokes sits below the laser line. The temperature must be derived from the absolute value of that shift and the measured intensity ratio. The Bose-Einstein population factor must be the exact form, not a high-temperature approximation.

Rebuild with `cd /app && go build -o bin/raman-temp ./cmd/raman-temp` and verify the binary exits 0 and produces deterministic output. Do not modify `/app/data/raman_spectrum.json`.

The report must conform to this JSON structure:

```json
{
  "sample": { "sample_id": "raman_calib_2025_001", "method": "stokes_anti_stokes_thermometry" },
  "parameters": {
    "laser_wavenumber": 0.0, "raman_shift_cm": 0.0,
    "bose_model": "", "frequency_exponent": 0.0, "temperature_offset": 0.0
  },
  "summary": {
    "stokes_peak_center": 0.0, "anti_stokes_peak_center": 0.0, "peak_shift": 0.0,
    "stokes_intensity": 0.0, "anti_stokes_intensity": 0.0,
    "stokes_anti_stokes_ratio": 0.0, "temperature_estimate": 0.0, "residual": 0.0
  }
}
```

`parameters.frequency_exponent` must be 4.0. The detected peak positions must be within 1 cm⁻¹ of the true maxima. The ratio must be within 5% of the value computed from detected intensities. The temperature must agree with the value independently computable from the detected shift and ratio to within 2 K.
