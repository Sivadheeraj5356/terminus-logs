# The canal transient simulator under `/app/environment` produces unstable and non

- **UUID:** `e2b3da3e-87b1-4dae-a515-46791e9911ec`
- **Slug:** `the-canal-transient-simulator-under-app-environment-produces`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The canal transient simulator under `/app/environment` produces unstable and non-conservative results when storage geometry changes, controls occur between output times, or a run is continued from a checkpoint. Repair the C++ `lockctl` implementation so `run`, `restore`, and `audit` follow the hydraulic and numerical contracts in `/app/environment/docs` and write the requested schema-version-4 report and optional restart snapshot.

The completed solver must use the documented nonlinear storage curves, hydraulic link laws, implicit midpoint/Newton method, adaptive step-doubling controller, exact event boundaries, and conservation accounting. A restored trajectory over append-only forcing must be identical to a clean trajectory over the same final inputs, while changed processed forcing or corrupt state must be rejected without changing existing outputs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
