# Asterism Color offline release pack

- **UUID:** `00370df0-ef0e-4c44-aa72-dce65f4d38db`
- **Slug:** `asterism-color-offline-release-pack`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Asterism Color offline release pack The foundry masters under `/app/foundry-sources` are sealed. Do not rewrite them, the FEA sources, color UFOs, or `/app/asterism-ledger` inputs.

Commission the offline release pack entrypoint named in `/app/asterism-spec/RELEASE_CONTRACT.md` so a default pack materializes `/app/out/colr-crate` from those masters using the pinned font toolchain already on PATH. Dropping finished fonts by hand is not enough: that pack command regenerates the crate, and checks re-run it before auditing the finished inventory.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
