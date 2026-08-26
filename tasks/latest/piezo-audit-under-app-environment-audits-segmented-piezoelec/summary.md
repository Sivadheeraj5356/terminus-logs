# `piezo-audit` under `/app/environment` audits segmented piezoelectric resonator

- **UUID:** `452ce15a-1ed6-4248-86f6-04f3c6e89e06`
- **Slug:** `piezo-audit-under-app-environment-audits-segmented-piezoelec`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

`piezo-audit` under `/app/environment` audits segmented piezoelectric resonator calibration files across multiple chip families against dated, inheritable profile catalogs. Published batch reports, branched manifest history, profile-graph caching, and resonance digests disagree with `/app/environment/docs/contract.md` after repeated runs.

Repair the Rust source under `/app/environment` so `cargo build --locked` produces a working `/app/environment/bin/piezo-audit`. The tool must parse chips with aliases, segments, and segment-level calibration overrides; resolve profiles with inheritance, effective-date revision selection, and deprecation windows; merge per-family `(chip_id, profile_id)` conflicts with last-file replacement; resolve alias collisions across the batch; maintain rollback-safe branched manifest history at `/app/output/resonance_manifest.json`; invalidate cached rows when either input bytes or the profile version fingerprint (`profile_graph_hash`) change; write output atomically on success; and compute schema v4 digests bound to profile lineage, provenance, and readings ordered by `(temp_c, line_index)`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
