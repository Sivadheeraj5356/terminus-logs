# Sandbox layout

- `cfg/sandbox_profile.toml` — profile generation defaults for recovery replay
- `driver/journal_runner.py` — single-pass journal digest helper
- `driver/recovery_runner.py` — live run, checkpoint, replay, observation export
- `fixtures/waves/recovery-wave.json` — audit wave consumed by `ops/probe/run-audit.sh`
- `lib/` — fuel, capability, escape, drift, and checkpoint helpers
- `ops/probe/run-audit.sh` — regenerates `/app/output/sandbox_observations.json`
- `structlib/wasm_runtime.py` — runtime orchestration for live and replay passes

Checkpoint state lands under `/app/data/wasm/checkpoint.json` during recovery audits.
