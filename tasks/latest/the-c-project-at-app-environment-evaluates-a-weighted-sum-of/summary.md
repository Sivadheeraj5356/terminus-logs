# The C project at /app/environment evaluates a weighted sum of Jacobi theta

- **UUID:** `7ccf5038-8247-4a95-824a-e84936464348`
- **Slug:** `the-c-project-at-app-environment-evaluates-a-weighted-sum-of`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The C project at /app/environment evaluates a weighted sum of Jacobi theta values. Each case gives N terms; term i has a coefficient c_i, an angle z_i, and a nome q_i, and the reported quantity is S = sum_{i=1}^{N} c_i * theta3(z_i, q_i),

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
