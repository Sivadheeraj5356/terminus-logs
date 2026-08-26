# The vibration-controls team has a multi-rate bench campaign from a closed-loop p

- **UUID:** `4649aef0-d039-4d9f-b743-fae06d562380`
- **Slug:** `the-vibration-controls-team-has-a-multi-rate-bench-campaign`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The vibration-controls team has a multi-rate bench campaign from a closed-loop pointing axis. Each capture contains the expected command response and the measured harmonic coordinates at several probes; the unexplained motion must be traced back through the calibrated sensitivity paths to the smallest exact set of source tones.

The campaign at `/app/plant_lab/` is read-only and must remain byte-for-byte unchanged. On completion, `/app/src/harmonic_recovery.cpp` is C++17 source and `/app/build/harmonic-recovery` is its executable.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
