# Production replays of the WASM sandbox report divergent digests after a profile-

- **UUID:** `4119dc2b-53d4-4212-b358-5d0588f28331`
- **Slug:** `production-replays-of-the-wasm-sandbox-report-divergent-dige`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Production replays of the WASM sandbox report divergent digests after a profile-generation bump: live execution completes, but checkpointed capability journals replay with stale fuel ledgers, token budgets, and drift scores. Fix sources under `/app/environment` so `/app/environment/ops/probe/run-audit.sh` regenerates `/app/output/sandbox_observations.json` with matching live and replay `sandbox_digest` values on consecutive runs.

The export carries `runs` (each with `sandbox_digest`, `metrics`, and `segments` tagged by subsystem `source`), plus `probes` with `live_digest`, `replay_digest`, `ledger_gap`, `stale_token_count`, and `escalation_delta`. Hand-written observations, test edits, wrapper-only shortcuts, and skipping the checkpoint directory are insufficient.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
