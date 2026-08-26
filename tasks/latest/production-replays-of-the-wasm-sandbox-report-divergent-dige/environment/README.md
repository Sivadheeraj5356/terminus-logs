# WASM Capability Sandbox Drift

Python simulator under `/app/environment` that executes WASM-like module journals under a fuel budget, gates host calls with expiring capability tokens, detects sandbox escape attempts, and tracks capability drift from baseline permissions.

- `structlib/wasm_runtime.py` — orchestrates module and host-call execution
- `driver/journal_runner.py` — replays scenario JSON and returns `{metrics, digest, valid}`

Operational contract: `/app/environment/docs/contract.md`.
