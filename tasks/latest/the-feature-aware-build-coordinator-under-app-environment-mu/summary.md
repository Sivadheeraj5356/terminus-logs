# The feature-aware build coordinator under `/app/environment` must certify that e

- **UUID:** `32e9eda8-d2a3-4e2d-9874-bd8335c3e03b`
- **Slug:** `the-feature-aware-build-coordinator-under-app-environment-mu`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The feature-aware build coordinator under `/app/environment` must certify that every expanded task graph stays acyclic across flag combinations. Primary arms in `/app/environment/docs/primary_flags.txt` look sound after `bash /app/environment/scripts/bp_run`, but held-out rows from `/app/environment/data/extra_flags.toml` show stuck counters or non-zero lag.

Echo pairs disagree on facet material, witness sidecars under `/app/output/witness_meta/` disagree with the JSON certificate, and the status probe can read steady while the report is incoherent.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
