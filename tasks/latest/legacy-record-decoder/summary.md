# # Legacy Record Decoder

- **UUID:** `ddff1202-d652-4e57-b812-a686e3c2e739`
- **Slug:** `legacy-record-decoder`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The decoder at `/app/environment` reads paired binary dumps and text exports, compares them for compatibility, and writes a validated bundle to `/app/output/legacy_record_bundle.json`. The pipeline is currently broken: decoded pairs are misreported as compatible when they diverge, malformed binary records pass silently instead of being flagged, and field extraction from the binary format is incorrect.

Fix the source under `/app/environment/src` and `/app/environment/tools` so the normal build-and-run sequence regenerates a correct bundle. The decoy modules ending in `_stub.rs` are alternate paths not on the active decoder.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
