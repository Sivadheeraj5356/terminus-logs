# Cold rebuilds print a clean driver status while loader output still drops requir

- **UUID:** `79664ae8-d24d-4937-bbce-87dff656db6b`
- **Slug:** `cold-rebuilds-print-a-clean-driver-status-while-loader-outpu`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Cold rebuilds print a clean driver status while loader output still drops required objects. Warm rebuilds look healthier, but manifest, journal, and loader surfaces disagree on ordering and availability.

Incremental bundle deltas can be missing from regenerated `/app/output/` JSON on runs that looked successful. Carry sidecars from an earlier profile or merge tier can pin the wrong wave label across later driver invocations in the same session.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
