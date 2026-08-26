# We've got an entropic mass-transfer lab under /app/environment. The Go and Rust

- **UUID:** `18179614-cdc5-4c21-af6f-62384a0b204d`
- **Slug:** `we-ve-got-an-entropic-mass-transfer-lab-under-app-environmen`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

We've got an entropic mass-transfer lab under /app/environment. The Go and Rust tree already builds four CLIs, but end-to-end runs still miss the behavioral contract in /app/environment/docs/mass_contract.txt.

Correct the sources under /app/environment so every public surface matches that contract. Hand-written files under /app/output are not enough.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
