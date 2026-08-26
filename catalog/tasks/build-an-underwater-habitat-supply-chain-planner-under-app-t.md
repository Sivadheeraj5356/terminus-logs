# Build an underwater habitat supply chain planner under /app that compiles missio

Submission: `ea3fa5f7-0a2b-46a8-af2a-9aae178000be`  
Slug: `build-an-underwater-habitat-supply-chain-planner-under-app-t`  
Latest archive: `ea3fa5f7-0a2b-46a8-af2a-9aae178000be_submission_2026-07-17T13_00_28.110Z.zip`  
Revisions: 4

## Task summary

Build an underwater habitat supply chain planner under /app that compiles mission cargo into a reproducible resupply build pipeline. The pipeline ingests mission workload under /app/data/mission, materializes dependency-ordered staging artifacts under /app/state through tide timing, berth assignment, cargo priority, cold-storage limits, lane window rules, and transfer certification, then exports deterministic resupply-plan.json and utilization-report.json under /app/output. Implement the habitat-resupply-ingest and habitat-resupply-export command-line tools: habitat-resupply-ingest reads the mission directory and writes validated staging artifacts; habitat-resupply-export compiles only certified staging into final build outputs without reopening raw mission inputs. Ingest must write seven staging files under /app/state: tide-snapshot.json, rov-index.json, berth-staging.json, transfer-cert.json, export-bind.json, o2-priority-freeze.json, and ingest-manifest.json. Each successful export must write /app/output/resupply-plan.json and /app/output/utilization-report.json and must persist /app/state/export-seal.json recording the frozen bind and plan fingerprint for the run. Each state and output artifact must include only the hash fields required by that artifact schema under /app/docs, and those values must match the digest definitions in the contract documents. Keep re-ingest stable on unchanged mission input and keep repeat exports byte-identical.

Required artifacts include: `/app/data/mission`, `/app/state`, `/app/output`, `/app/output/resupply-plan.json`, `/app/output/utilization-report.json`, `/app/state/export-seal.json`, `/app/docs`, `/app/lib`.

Author anonymous tagged this **hard** build-and-dependency-management task (habitat-resupply, tide-scheduling, berth-planning, bash-cli, staging-export).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `ea3fa5f7-0a2b-46a8-af2a-9aae178000be_submission_2026-07-17T13_00_28.110Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
