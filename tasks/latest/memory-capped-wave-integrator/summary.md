# # Memory-Capped Wave Integrator

- **UUID:** `2d279cd7-0cc2-4696-b247-54885b07bce3`
- **Slug:** `memory-capped-wave-integrator`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Node integrator under `/app/` shows these symptoms in verifier workloads: The normal `run_entry.js` pipeline must regenerate traces from config; static or manual output writes are insufficient. Fix source code under `/app/` per the contract subsystem scope.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
