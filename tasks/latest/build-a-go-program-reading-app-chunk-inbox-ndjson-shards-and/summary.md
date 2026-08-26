# Build a Go program reading /app/chunk_inbox NDJSON shards and writing /app/outpu

- **UUID:** `a1135886-b3ce-495d-a9a8-6da04959ce8f`
- **Slug:** `build-a-go-program-reading-app-chunk-inbox-ndjson-shards-and`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Build a Go program reading /app/chunk_inbox NDJSON shards and writing /app/output/expected.json. Envelope: chunk_id, tenant_id, object_id, chunk_offset, size_bytes, hash, content_fingerprint, algorithm, refcount, registered_ts, tier, seal.

Optional: force_admit, force_reject, schema_version, op. Tables in /app/dedup_arena, /app/hash_codec, /app/tier_dialer, /app/quarantine_cell, /app/cycle_witness, /app/tenant_oracle, /app/object_graph.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
