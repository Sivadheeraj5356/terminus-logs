# Restore envelope custody qualification in `/app` and publish `/output/recovery-s

- **UUID:** `160a718f-940b-4072-b6cf-373b99176c14`
- **Slug:** `restore-envelope-custody-qualification-in-app-and-publish-ou`
- **Category:** security
- **Difficulty:** hard

## Summary

Restore envelope custody qualification in `/app` and publish `/output/recovery-set` from `/app/vault` using the cryptographic protocols in `/app/docs`. The completed recovery set must contain recovered objects under `/output/recovery-set/objects`, a path-sorted `/output/recovery-set/inventory.jsonl`, `/output/recovery-set/recovery-root.json`, and `/output/recovery-set/audit.dsse.json` as documented.

Qualification must honor historical custody authority at each object's epoch, committed rewrap lineage (including rollbacks), distinct authorized organizations, version-specific envelope identity, complete evidence snapshots, resumable checkpoint safety, source immutability, and atomic publication without provisional plaintext. `/output/recovery-set/recovery-root.json` must include `schema_version`, `policy_id`, `evidence_snapshot_sha256`, `inventory_sha256`, and `recovery_root`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
