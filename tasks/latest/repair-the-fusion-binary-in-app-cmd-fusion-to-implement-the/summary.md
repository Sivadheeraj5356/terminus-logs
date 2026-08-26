# Repair the `fusion` binary in `/app/cmd/fusion` to implement the contract in `/a

- **UUID:** `faee0d15-8a98-4b88-8538-d03b625f3af7`
- **Slug:** `repair-the-fusion-binary-in-app-cmd-fusion-to-implement-the`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Repair the `fusion` binary in `/app/cmd/fusion` to implement the contract in `/app/docs/auroral-lattice-contract.md`. The repaired binary must support this invocation: `fusion --telemetry-dir /app/telemetry --calibration-dir /app/calibration --probe /app/probe/driftprobe --probe-batch /app/telemetry/public.cfr --out /app/output/events.tsv --audit-out /app/output/audit.json`

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
