# # Quota supervisor drift after unclean shutdown

- **UUID:** `666e51d2-cacf-4f2d-b4cc-7080dde6666b`
- **Slug:** `quota-supervisor-drift-after-unclean-shutdown`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Storage operators finished an emergency reboot of the local quota control plane, but fleet state still disagrees with itself. `/app/bin/client_t4 list` reports hard limits that diverge from `/app/environment/data/q9/rows_q2.json`, sidecar stamps under `/app/environment/data/m9/` lag sealed generations, and deferred journal tails under `/app/environment/data/j4/` can resurrect limits for labels already retired in the catalog.

Restore correct cold-boot recovery through the deployed operator toolchain under `/app/environment` so `/app/bin/ctl_s8 recover-all` completes cleanly, then rebuild with `/app/environment/scripts/build_all.sh`. Wrapper-only edits or static writes under `/app/output` are insufficient; graded artifacts must come from the normal admin pipeline.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
