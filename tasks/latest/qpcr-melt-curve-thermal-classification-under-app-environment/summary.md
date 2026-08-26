# qPCR melt-curve thermal classification under `/app/environment` must discharge f

- **UUID:** `70025929-7ec4-4264-b5f7-af477cfbe171`
- **Slug:** `qpcr-melt-curve-thermal-classification-under-app-environment`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

qPCR melt-curve thermal classification under `/app/environment` must discharge floating-point numeric policy for laboratory assays that arrive through an append-only observation journal. Measured melt temperatures relative to uplink setpoints must classify stress wells and band wells under the published tolerance policy.

Active assay observations must stay stable when journal lines are reordered or transport-retried. Policy swaps must recompute thermal outcomes rather than reuse stale numeric products.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
