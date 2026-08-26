# Implement `SpectralAnalyzer#run!` to drive the full spectroscopy pipeline. It sh

- **UUID:** `7dfe4024-4b20-4236-b7bd-d493d89eeffe`
- **Slug:** `implement-spectralanalyzer-run-to-drive-the-full-spectroscop`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Implement `SpectralAnalyzer#run!` to drive the full spectroscopy pipeline. It should fetch simulation data from the API on port 3000, compute spectral metrics, and write the analysis artifacts described in `/app/docs/manual_workflow.md`.

The sensor identifier is set in the Containerfile at `/app/Containerfile` as `SENSOR_ID`. Use its value (e.g., `ACCEL-001`) to construct output filenames.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
