# fxctl under `/app/environment` finishes the parquet column encryption metadata d

- **UUID:** `5eebc7cb-8880-4787-9636-dd8fb5c7d563`
- **Slug:** `fxctl-under-app-environment-finishes-the-parquet-column-encr`
- **Category:** security
- **Difficulty:** hard

## Summary

fxctl under `/app/environment` finishes the parquet column encryption metadata desk. The desk reads encrypted column blobs from `/app/environment/payload/`, resolves lane authority and column-key epochs from the durable ring at `/app/environment/payload/ring_seg.bin`, unwraps segment bytes with per-group AAD plus key material, and writes `/app/output/sync_record.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
