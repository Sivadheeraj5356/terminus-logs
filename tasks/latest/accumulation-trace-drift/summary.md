# # Accumulation Trace Drift

- **UUID:** `ed3ed486-f775-46c4-b0d1-3b12f00ce93c`
- **Slug:** `accumulation-trace-drift`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The training runtime under /app/environment emits JSONL run records and per-pass JSON summaries under /app/output. Serial runs look consistent.

Under concurrent admission with snapshot/continue — including partial-window halts mid accum window — norm summaries often stay within plan tolerance while pass files disagree with a serial baseline for the same plan, seed, and accum window. Fix the Rust sources under /app/environment so the pipeline regenerates correct evidence.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
