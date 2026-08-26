Production replays of the WASM sandbox report divergent digests after a profile-generation bump: live execution completes, but checkpointed capability journals replay with stale fuel ledgers, token budgets, and drift scores.

Fix sources under `/app/environment` so `/app/environment/ops/probe/run-audit.sh` regenerates `/app/output/sandbox_observations.json` with matching live and replay `sandbox_digest` values on consecutive runs. The export carries `runs` (each with `sandbox_digest`, `metrics`, and `segments` tagged by subsystem `source`), plus `probes` with `live_digest`, `replay_digest`, `ledger_gap`, `stale_token_count`, and `escalation_delta`. Hand-written observations, test edits, wrapper-only shortcuts, and skipping the checkpoint directory are insufficient.

Journal scenarios under `/tests/fixtures/wasm/` still replay through `/app/environment/driver/journal_runner.py` for single-pass checks. Field semantics, metrics tuple order, probe map keys, segment `source` literals, digest rules, and the recovery-wave witness file are in `/app/environment/docs/contract.md`.

`WasmRuntime.run()` returns metrics as a five-int tuple `(executed, fuel_used, violations, escapes, cap_drift)` — do not wrap it in a dict or add fields. Digest is `SHA256(repr(metrics))[:16]`.
