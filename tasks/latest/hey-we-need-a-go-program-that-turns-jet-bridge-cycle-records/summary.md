# Hey, we need a Go program that turns jet bridge cycle records into per cycle bil

- **UUID:** `398ef4f2-7500-4671-845d-882590277f5e`
- **Slug:** `hey-we-need-a-go-program-that-turns-jet-bridge-cycle-records`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Hey, we need a Go program that turns jet bridge cycle records into per cycle billing lines and a per carrier summary. Records sit in ndjson under /app (or AIRBRIDGE_DATA); outputs go to /app/output (or AIRBRIDGE_OUT).

feebook holds rates, caps, uplift, and the off hours window. Read every doc under codex, handbook, tower_logs; output_shapes and cycle_codex first.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
