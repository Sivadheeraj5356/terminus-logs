# After a workload tier move, cgroup totals look healthy while policy traces still

- **UUID:** `d64d2df4-2da6-484d-9f3d-bd6ede26e425`
- **Slug:** `after-a-workload-tier-move-cgroup-totals-look-healthy-while`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

After a workload tier move, cgroup totals look healthy while policy traces still attribute events to the old boundary. Fix sources under `/app/environment` and build with `make -C /app/environment all`.

Run `/app/environment/tools/j4_round --round`, tail recovery with `--tail`, and emit with `/app/environment/tools/p7_emit --out /app/output/observ_trace.json`. Tick uses tick_apply `--site`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
