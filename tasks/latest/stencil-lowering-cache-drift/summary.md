# # Stencil lowering cache drift

- **UUID:** `18f85dc7-9228-4799-83a0-dd01b5ee2d16`
- **Slug:** `stencil-lowering-cache-drift`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Our grid-operator compiler in `/app/environment` keeps a replay journal beside the build cache and a migration WAL under `/app/output/.cache/`. Incremental compiles have been drifting: spill totals change on repeated stage-two cache hits, migration leaves stale stage rows behind, WAL segments disagree with the journal epoch, replay generations diverge from the replay log, metrics rollups diverge from the live trace, and poisoned digest rows sometimes override a fresh recompute.

Repair `/app/environment` so `node /app/environment/cli/driver.mjs compile --spec /app/environment/specs/operator.json --out /app/output` regenerates `/app/output/kernel.mjs`, `/app/output/pass.trace.json`, and `/app/output/metrics.json`. Static or manual writes to `/app/output` are not sufficient; hand-editing those outputs or bypassing the driver is not acceptable.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
