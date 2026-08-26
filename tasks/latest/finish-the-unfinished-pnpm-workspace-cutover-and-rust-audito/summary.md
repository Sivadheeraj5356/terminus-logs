# Finish the unfinished pnpm workspace cutover and Rust auditor under /app. Overri

- **UUID:** `ecf8e7f3-557e-4c68-be27-a2d8011d80e9`
- **Slug:** `finish-the-unfinished-pnpm-workspace-cutover-and-rust-audito`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

Finish the unfinished pnpm workspace cutover and Rust auditor under /app. Overrides still hit public registry, store may be stubbed, lockfile digests drift, provides collide, and packaging is unfinished.

Deliverables: repair overrides/deps.csv; implement `pnpmfix inspect`; finish fail-closed release.sh.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
