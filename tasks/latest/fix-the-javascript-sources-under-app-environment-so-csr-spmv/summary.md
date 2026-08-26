# Fix the JavaScript sources under /app/environment so CSR SpMV stays under the no

- **UUID:** `aec3ecd3-10d8-443a-a1e5-7b3507b42c24`
- **Slug:** `fix-the-javascript-sources-under-app-environment-so-csr-spmv`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Fix the JavaScript sources under /app/environment so CSR SpMV stays under the nonzero cap in /app/environment/docs/nlim.toml, and residual norms for every pack under /app/environment/suite land inside the absolute and relative bands published there (and in each pack meta.toml). Run this probe command

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
