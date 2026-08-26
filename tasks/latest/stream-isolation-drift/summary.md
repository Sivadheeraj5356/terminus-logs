# # Stream Isolation Drift

- **UUID:** `59d3bc9c-831c-46e5-b51d-21201678874b`
- **Slug:** `stream-isolation-drift`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The derivative runtime under /app/environment emits JSONL run records and per-pass JSON summaries under /app/output. Serial runs look consistent.

Under concurrent admission with checkpoint continue, norm summaries often stay within plan tolerance while pass files disagree with a serial baseline for the same plan, seed, and mode. Fix the source under /app/environment so the pipeline regenerates correct evidence.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
