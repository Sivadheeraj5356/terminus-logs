# # Vaccine cold-chain lot-wave planner

- **UUID:** `a5dd6a73-2e23-40d3-9ced-545b33c975c1`
- **Slug:** `vaccine-cold-chain-lot-wave-planner`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Scientific-computing vaccine cold-chain lot-wave planner. Immunolab fixtures under /app/data/immunolab/ and policy in /app/config/immuno.toml drive wave-3 allocation through the immunoflow planner at /app/environment.

On the canonical chain, the public products under /app/output/ and persisted ledgers under /app/var/ disagree with each other and with independent replay of /app/environment/docs/contract.md. Implementation under /app/environment must be corrected so the normal immunoflow pipeline regenerates consistent artifacts.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
