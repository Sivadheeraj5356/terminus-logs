# You're in `/app`, a TOF mass spectrometry metrology bench that reconciles compet

- **UUID:** `57f64195-039c-4caa-a97b-07976b6bc740`
- **Slug:** `you-re-in-app-a-tof-mass-spectrometry-metrology-bench-that-r`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

You're in `/app`, a TOF mass spectrometry metrology bench that reconciles competing flight-time calibrations into a cubic mass axis for ESI-L ladder shots. Instrument telemetry for the production shot is reachable through the local interface under `/app/instrument`.

Competing bench axis candidates with correlated coefficient uncertainties are recorded under `/app/docs/lab-notes/`. Numerical evaluation runs through `/app/bin/tofmass`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
