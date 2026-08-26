# The retention QC code under `/app/environment` has started producing lineage-dep

- **UUID:** `62937445-db90-42ef-81b9-b9f083e3bf6a`
- **Slug:** `the-retention-qc-code-under-app-environment-has-started-prod`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The retention QC code under `/app/environment` has started producing lineage-dependent attestations. Results change with harmless shard layouts, default leave-one-run-out records disagree with isolated runs, and some local edits alter unrelated records.

Repair the Go source code under `/app/environment` so it follows `/app/environment/docs/ra_contract.md` for CELL/3 identity, normalized coordinates, model fitting, finite-sample coverage, lineage, canonical closure, and atomic errors. The normal command is `/app/environment/tools/ra_run --emit-attestation /app/output/attestation_pack.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
