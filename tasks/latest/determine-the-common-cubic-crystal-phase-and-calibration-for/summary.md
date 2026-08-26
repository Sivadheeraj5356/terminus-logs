# Determine the common cubic crystal phase and calibration for the two diffraction

- **UUID:** `196fc576-d7d7-4772-9e89-d6e02ad15939`
- **Slug:** `determine-the-common-cubic-crystal-phase-and-calibration-for`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Determine the common cubic crystal phase and calibration for the two diffraction scans in a study. The command is `/app/bin/cubic-index --study STUDY_PATH --output OUTPUT_PATH`.

The study format, reflection rules, feasibility conditions, objective order, canonical tie-breaking, JSON certificate, diagnostics, limits, and publication behavior are defined in `/app/CUBIC_DIFFRACTION_PROTOCOL.md`. Implement the scientific indexing calculation in `/app/src/indexer.rs`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
