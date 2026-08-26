# I have a batch of one-dimensional quantum wells and I need the low-lying bound-s

- **UUID:** `5f826675-34fb-488a-ae7d-b18f091ba670`
- **Slug:** `i-have-a-batch-of-one-dimensional-quantum-wells-and-i-need-t`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

I have a batch of one-dimensional quantum wells and I need the low-lying bound-state energies for each of them. A well is a single particle in a potential V(x), governed by the time-independent equation -1/2 * psi''(x) + V(x) * psi(x) = E * psi(x) (hbar = m = 1)

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
