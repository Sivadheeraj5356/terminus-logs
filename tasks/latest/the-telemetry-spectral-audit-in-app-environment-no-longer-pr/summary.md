# The telemetry spectral audit in `/app/environment` no longer produces reproducib

- **UUID:** `d1077eb1-a6a7-4f98-ba15-b647f105b0ac`
- **Slug:** `the-telemetry-spectral-audit-in-app-environment-no-longer-pr`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The telemetry spectral audit in `/app/environment` no longer produces reproducible reports after revisioned schema-version 3 packs and resumable processing were introduced. Repair `/app/bin/hann_energy_audit` so it conforms to `/app/docs/contract.md`, `/app/docs/pack-v3.md`, `/app/docs/spectral-processing.md`, and `/app/docs/checkpoint-and-seals.md`, while preserving the documented schema-version 2 behavior.

It must deterministically replay sample and calibration revisions, reconstruct and calibrate sparse timelines, apply the documented frame-quality, gap, detrending, Hann, Goertzel, weighted-band, and peak rules, and emit the canonical report and seals. The audit report at `/app/output/report.json` must carry top-level `schema_version`, ordered `scenarios`, and a `summary` object as specified in the contract docs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
