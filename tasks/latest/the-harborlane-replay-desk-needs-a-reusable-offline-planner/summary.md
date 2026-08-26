# The harborlane replay desk needs a reusable offline planner, not a one-off plan

- **UUID:** `df101f67-b1f1-41ce-b7fa-5b65d20e1d7e`
- **Slug:** `the-harborlane-replay-desk-needs-a-reusable-offline-planner`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The harborlane replay desk needs a reusable offline planner, not a one-off plan for the sample files. Finish the Haskell program at `/app/Main.hs`; it will be compiled with GHC and run as `/tmp/harborlane-planner --root ROOT --out-dir OUT_DIR`.

For each `ROOT`, read `ROOT/var/lib/harborlane/data/segments.tsv`, `ROOT/var/lib/harborlane/data/replay.tsv`, `ROOT/var/lib/harborlane/data/conflicts.tsv`, `ROOT/etc/harborlane/policy.tsv`, and `ROOT/var/cache/harborlane/state/leases.tsv`. Write `OUT_DIR/plan.tsv` and `OUT_DIR/Plan.hs`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
