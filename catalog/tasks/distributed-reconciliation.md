# distributed_reconciliation

Submission: `6048e9db-9c3f-4f9e-8e46-d5071d783500`  
Slug: `distributed-reconciliation`  
Latest archive: `6048e9db-9c3f-4f9e-8e46-d5071d783500_submission_2026-07-05T16_03_06.426Z.zip`  
Revisions in Dropbox: 2

## Task summary

Update Go source under `/app/environment` to implement functions marked `// Stub:` in the coordination packages. The discrete-event driver (`/app/environment/internal/pipeline/run.go`), profile loader, fixture catalog, audit writer, metrics helpers, runner shell, bundled profiles, and offline verifier digest helpers are provided. Complete stub packages per `/app/environment/docs/build_obligations.md` so bundled profiles produce `/app/output/schedule_audit.json` matching `/app/environment/docs/schedule_audit_schema.md`. The image is offline (`allow_internet = false`). Start with `/app/environment/docs/build_obligations.md`, then read `/app/environment/docs/schedule_audit_schema.md`, `/app/environment/docs/graph_layout.md`, and `/app/environment/docs/operations.md`.

Required artifacts include: `/app/environment`, `/app/environment/internal/pipeline/run.go`, `/app/environment/docs/build_obligations.md`, `/app/output/schedule_audit.json`, `/app/environment/docs/schedule_audit_schema.md`, `/app/environment/docs/graph_layout.md`, `/app/environment/docs/operations.md`, `/app/output/scheduler_lane_state.json`.

Author anonymous tagged this **hard** data-processing task (distributed-systems, scheduling, dependency-graph, checkpoint-resume, schedule-audit, go).

Time estimates: expert ~720 min, junior ~1440 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `6048e9db-9c3f-4f9e-8e46-d5071d783500_submission_2026-07-05T16_03_06.426Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
