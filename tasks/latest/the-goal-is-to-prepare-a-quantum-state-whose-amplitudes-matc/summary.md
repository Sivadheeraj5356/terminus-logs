# The goal is to prepare a quantum state whose amplitudes match a supplied real pr

- **UUID:** `73a7d8dd-cdc8-4b15-8390-5a3740b19f39`
- **Slug:** `the-goal-is-to-prepare-a-quantum-state-whose-amplitudes-matc`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

The goal is to prepare a quantum state whose amplitudes match a supplied real profile. A solution reads a specification and emits a circuit that builds the requested state on a register starting in the all zeros state.

The specification is a text file. Its first line holds a width n.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
