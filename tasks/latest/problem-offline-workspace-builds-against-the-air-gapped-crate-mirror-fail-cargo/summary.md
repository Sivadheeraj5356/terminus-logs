# ## Problem

- **UUID:** `737acf18-05b5-4c2b-a6b9-42ddfd52315c`
- **Slug:** `problem-offline-workspace-builds-against-the-air-gapped-crate-mirror-fail-cargo`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Offline workspace builds against the air-gapped crate mirror fail. `cargo build --offline --locked` cannot resolve or verify the packages listed for this lane even though crate tarballs appear present under the mirror trees.

A discarded sync snapshot under `/app/data/mirror-stale` still looks plausible and must not be trusted as the active registry. Restore offline Cargo source replacement and the active local registry so the documented offline build succeeds for every primary package id.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
