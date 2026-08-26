# Numerically integrate the stiff mass-action reaction networks that the Halvard k

- **UUID:** `53b0bd56-418d-4b64-abb6-10d4248104fc`
- **Slug:** `numerically-integrate-the-stiff-mass-action-reaction-network`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Numerically integrate the stiff mass-action reaction networks that the Halvard kinetics bench certifies. Each network file names its species, its elementary reactions and rate constants, its initial concentrations, its horizon and its error tolerances.

The bench at /app/bench/bench still integrates the twelve calibration systems compiled into it; /app/calibration holds those same twelve as files. Uncertified assay networks sit in /app/assay.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
