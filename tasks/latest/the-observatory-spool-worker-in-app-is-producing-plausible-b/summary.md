# The observatory spool worker in `/app` is producing plausible but incorrect spec

- **UUID:** `daac4834-00ef-4f4e-825e-a151fc042820`
- **Slug:** `the-observatory-spool-worker-in-app-is-producing-plausible-b`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The observatory spool worker in `/app` is producing plausible but incorrect spectral-drift records from bundled SPECZ frames, and interrupted runs can duplicate or skip scans. The public entry point is `/app/bin/specz-worker` (symlink to `/app/scripts/specz-worker`).

Repair that AWK/Bash worker and its `/app/lib` modules so it processes valid `*.spz` files from `/data/inbox`, recovers stale work from `/data/work`, and follows the current frame, calibration, statistics, configuration, and recovery rules in `/app/docs/observatory-operations-notebook.md`, `/app/container/specz-worker.def`, and `/app/docs/operator-runbook.md`. Both documented frame revisions must remain supported.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
