# Storage operators report that thin-provisioned volumes still show high utilizati

- **UUID:** `fea51224-f694-463a-9acb-3bb06d53d171`
- **Slug:** `storage-operators-report-that-thin-provisioned-volumes-still`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Storage operators report that thin-provisioned volumes still show high utilization after trim replay exits zero. Guest trim logs discarded ranges, but chunk inventory exports show no reclaimable slot change.

Array trim telemetry reports cleared extents while the volume free-map digest stays on a prior epoch. A second replay window fails convergence: trim transcripts, digests, propagation traces, checkpoint persistence, and staging revision disagree.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
