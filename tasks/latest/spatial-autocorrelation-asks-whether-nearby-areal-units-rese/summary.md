# Spatial autocorrelation asks whether nearby areal units resemble one another mor

- **UUID:** `207f76a5-b1a3-4cff-95fe-a4ec28a94a3e`
- **Slug:** `spatial-autocorrelation-asks-whether-nearby-areal-units-rese`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Spatial autocorrelation asks whether nearby areal units resemble one another more than chance allows. Here a map of U.S.

counties carries two attributes (a binary label, black (1) or white (0), and an integer numeric value) together with a disclosed binary contiguity edge list that defines the first-order neighbour matrix W1. We want three classic diagnostics computed exactly and read off the same weight geometry, so that the neighbour structure is shared and any error in it propagates.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
