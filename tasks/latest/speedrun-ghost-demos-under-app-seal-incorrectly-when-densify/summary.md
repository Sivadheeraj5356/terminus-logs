# Speedrun ghost demos under `/app` seal incorrectly when densify packing and inde

- **UUID:** `6e0cf6ff-faf1-431f-9a90-0135f6858277`
- **Slug:** `speedrun-ghost-demos-under-app-seal-incorrectly-when-densify`
- **Category:** games
- **Difficulty:** hard

## Summary

Speedrun ghost demos under `/app` seal incorrectly when densify packing and independent replay diverge. Fix the Java library sources under `/app/environment` so `bash /app/driver/emit_ghost.sh` (also `/app/environment/driver/emit_ghost.sh`) rebuilds a valid `/app/output/ghost_seal.json` from `/app/data/annex_slice36`, band profiles under `/app/data/bands/profiles`, and `/app/fixtures/closed_algebra.json`.

Digest and densify rules live in `/app/docs/pol_contract.md`. The checker recompiles `sep_tool`, `fold_tool`, and `tie_tool` with javac from the libraries under `/app` and runs those tools.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
