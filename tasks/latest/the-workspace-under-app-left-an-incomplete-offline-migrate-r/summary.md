# The workspace under `/app` left an incomplete offline migrate: release-train sel

- **UUID:** `75810cea-7647-47ec-ba76-2ecdd18bac3f`
- **Slug:** `the-workspace-under-app-left-an-incomplete-offline-migrate-r`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The workspace under `/app` left an incomplete offline migrate: release-train selection, channel windows, extension peer closure, content-addressed store packing, and the migrate journal no longer converge. Frozen installs and seal audits fail after the interrupted cycle in this pnpm monorepo lab.

Correct the migrate pipeline sources under `/app` so `/app/tools/pnpm run verify:all` succeeds (resume, seal, offline frozen install, build, and `/app/tools/pnpm run audit:seal`). Follow `/app/docs/offline-workflow.md`, `/app/docs/train-contract.md`, `/app/docs/channel-contract.md`, `/app/docs/extension-contract.md`, `/app/docs/pack-contract.md`, and `/app/docs/journal-contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
