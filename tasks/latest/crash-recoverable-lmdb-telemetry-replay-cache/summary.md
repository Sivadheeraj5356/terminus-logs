# # Crash-recoverable LMDB telemetry replay cache

- **UUID:** `46956eb6-df4f-442e-af66-72dc8af07788`
- **Slug:** `crash-recoverable-lmdb-telemetry-replay-cache`
- **Category:** data-processing
- **Difficulty:** medium

## Summary

Repair the C telemetry replayer under `/app`. A recent persistence integration caused replay results to diverge between fresh, resumed, forced, and concurrent executions.

Restore the documented behavior while preserving the native C/LMDB architecture and the existing command-line interface. The behavioral contract is distributed across the visible files under `/app/docs`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
