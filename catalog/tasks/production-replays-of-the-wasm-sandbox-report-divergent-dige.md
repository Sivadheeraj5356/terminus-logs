# Production replays of the WASM sandbox report divergent digests after a profile-

Submission: `4119dc2b-53d4-4212-b358-5d0588f28331`  
Slug: `production-replays-of-the-wasm-sandbox-report-divergent-dige`  
Latest archive: `4119dc2b-53d4-4212-b358-5d0588f28331_submission_2026-07-09T13_17_03.929Z.zip`  
Revisions in Dropbox: 1

## Task summary

Production replays of the WASM sandbox report divergent digests after a profile-generation bump: live execution completes, but checkpointed capability journals replay with stale fuel ledgers, token budgets, and drift scores. Fix sources under `/app/environment` so `/app/environment/ops/probe/run-audit.sh` regenerates `/app/output/sandbox_observations.json` with matching live and replay `sandbox_digest` values on consecutive runs. The export carries `runs` (each with `sandbox_digest`, `metrics`, and `segments` tagged by subsystem `source`), plus `probes` with `live_digest`, `replay_digest`, `ledger_gap`, `stale_token_count`, and `escalation_delta`. Hand-written observations, test edits, wrapper-only shortcuts, and skipping the checkpoint directory are insufficient.

Required artifacts include: `/app/environment`, `/app/environment/ops/probe/run-audit.sh`, `/app/output/sandbox_observations.json`, `/app/environment/driver/journal_runner.py`, `/app/environment/docs/contract.md`.

Author anonymous tagged this **hard** data-processing task (python, wasm, sandbox, capability, fuel).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `4119dc2b-53d4-4212-b358-5d0588f28331_submission_2026-07-09T13_17_03.929Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
