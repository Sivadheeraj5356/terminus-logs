# The Raman thermometry package at `/app` computes temperature from Stokes/anti-St

- **UUID:** `948b1f30-f154-4afc-af02-1a5d43fdeeff`
- **Slug:** `the-raman-thermometry-package-at-app-computes-temperature-fr`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Raman thermometry package at `/app` computes temperature from Stokes/anti-Stokes intensity ratios for sample `raman_calib_2025_001`. The output report at `/app/output/report.json` currently gives physically wrong temperatures — the reported value is inconsistent with the detected peak positions and intensity ratio in the spectrum.

Fix the code so the reported temperature is physically consistent with the measured spectrum. Specifically, the Stokes and anti-Stokes peaks should each be detected as the single highest-intensity point within ±15 cm⁻¹ of their expected positions.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
