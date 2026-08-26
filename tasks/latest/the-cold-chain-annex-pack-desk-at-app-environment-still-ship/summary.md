# The cold-chain annex pack desk at `/app/environment` still ships broken hardened

- **UUID:** `3200b371-1bb2-4bf4-ad97-3b3b97cf68f1`
- **Slug:** `the-cold-chain-annex-pack-desk-at-app-environment-still-ship`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The cold-chain annex pack desk at `/app/environment` still ships broken hardened packs. Fix the local toolchain sources under `/app/environment` so rebuilds stay correct; module-level helpers used by that pipeline must behave correctly, not only the driver exit status.

Hand-written static pack files are not enough; the verifier regenerates packs through the normal rebuild path and rejects output-only edits. `/app/h7p/pp_run rebuild` (same binary as `/app/environment/h7p/pp_run rebuild`) finishes and the aggregate ledger totals still match the fixture sums, but per-row dependency pins and ABI slots disagree with the held-out rotations in `/app/environment/data/rot_tbl.toml`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
