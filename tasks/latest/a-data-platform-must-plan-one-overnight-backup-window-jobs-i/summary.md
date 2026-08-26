# A data platform must plan one overnight backup window. Jobs include snapshots, v

- **UUID:** `dd7705eb-9118-46a8-8765-b0812d7ebbc4`
- **Slug:** `a-data-platform-must-plan-one-overnight-backup-window-jobs-i`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A data platform must plan one overnight backup window. Jobs include snapshots, validations, compactions, and cross-region replications.

Some jobs are mandatory, some are optional but improve restore coverage. Jobs form a dependency DAG and consume worker CPU, global network, and scratch storage over time.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
