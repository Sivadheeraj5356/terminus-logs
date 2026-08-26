# The lab's checkpointed integrator ships a broken `demo_engine` binary under `/ap

- **UUID:** `2b91c159-9be4-4c7d-b84b-b6d07a60e069`
- **Slug:** `the-lab-s-checkpointed-integrator-ships-a-broken-demo-engine`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The lab's checkpointed integrator ships a broken `demo_engine` binary under `/app/build`. Coupled defects across checkpoint restore, pair-evaluation ledger accounting, periodic wrap crossing tally, journal CRC folding, and wrap-epoch reduction leave recovery reports off-spec.

Repair the C++ sources under `/app/environment` so a clean CMake release rebuild produces a deterministic emitter again. Run `/app/build/demo_engine emit <scene_token> /app/output/recovery_report.json` after rebuilding from `/app/environment`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
