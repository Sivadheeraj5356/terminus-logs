# Infer the exact maximum-posterior physical history of a repeated-round planar st

- **UUID:** `2ad50431-6057-47a4-9522-48ee134dfb71`
- **Slug:** `infer-the-exact-maximum-posterior-physical-history-of-a-repe`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Infer the exact maximum-posterior physical history of a repeated-round planar stabilizer experiment. The observed syndrome changes can arise from local Pauli occurrences, delayed signatures from earlier occurrences, a persistent readout frame, and latent thermal or control-line burst sources that emit across several rounds.

Determine the complete minimum-energy likelihood manifold and its joint logical-coset degeneracy. A burst source is selected once for the whole experiment, not independently in each observation round.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
