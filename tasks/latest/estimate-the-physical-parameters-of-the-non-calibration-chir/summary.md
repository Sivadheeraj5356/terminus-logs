# Estimate the physical parameters of the non-calibration chirped spectral sources

- **UUID:** `7d73c410-0195-4b91-88ff-76496407c011`
- **Slug:** `estimate-the-physical-parameters-of-the-non-calibration-chir`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Estimate the physical parameters of the non-calibration chirped spectral sources present in `/app/observations/`. The array samples below Nyquist, so the same source can appear as different aliases across instruments, and true source frequencies are not limited to any single instrument's observed baseband.

`/app/catalog.sqlite` supplies the instrument clocks and calibration tones needed for the inverse spectral fit; calibration tones are references for the fit and must not be reported as unknown sources. Write the merged source estimates to `/app/output/events.json` and `/app/output/recovered.sqlite`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
