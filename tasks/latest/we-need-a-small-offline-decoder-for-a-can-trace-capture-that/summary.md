# We need a small offline decoder for a CAN trace capture that came off a bench ri

- **UUID:** `f8becc32-e9a1-4cf0-9b03-f99c5ce299b0`
- **Slug:** `we-need-a-small-offline-decoder-for-a-can-trace-capture-that`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

We need a small offline decoder for a CAN trace capture that came off a bench rig. Build a Go CLI at `/app/cantrace` that reads the network description and binary trace, applies the validation rules in `/app/task_file/cantrace-format.md`, and writes the JSON report.

Running `/app/cantrace` with no arguments must read `/app/task_file/network.json` and `/app/task_file/public_trace.bin`, then write `/app/out/report.json`. Running `/app/cantrace <network.json> <trace.bin> <report.json>` must do the same job for another compatible capture.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
