# Greenhouse fertigation operators report dose logs accepted out of file order, EC

Submission: `01cff40c-609f-4f5c-b4ed-b1f05e1adadd`  
Slug: `greenhouse-fertigation-operators-report-dose-logs-accepted-o`  
Latest archive: `01cff40c-609f-4f5c-b4ed-b1f05e1adadd_submission_2026-07-07T07_46_18.228Z.zip`  
Revisions: 5

## Task summary

Greenhouse fertigation operators report dose logs accepted out of file order, EC drift checks that ignore the lead-in window after batch open, compliance exports missing or wrong integrity hashes, and daily volume totals that drift when batches replay on the same SQLite file. Repair and recompile the Go fert-ingest and fert-export binaries from /app using /app/scripts/build.sh with CGO_ENABLED and go.mod dependencies. Behavior must match /app/docs/event-format.md, /app/docs/fertigation-rules.md, /app/docs/db-schema.md, /app/docs/audit-report-schema.md, /app/docs/cli-contract.md, and /app/config/greenhouse-profile.json. Write compliance export to /app/output/fertigation-compliance.json.

Required artifacts include: `/app/scripts/build.sh`, `/app/docs/event-format.md`, `/app/docs/fertigation-rules.md`, `/app/docs/db-schema.md`, `/app/docs/audit-report-schema.md`, `/app/docs/cli-contract.md`, `/app/config/greenhouse-profile.json`, `/app/output/fertigation-compliance.json`.

Author anonymous tagged this **hard** build-and-dependency-management task (greenhouse, sqlite, go, fertigation, jsonl).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `01cff40c-609f-4f5c-b4ed-b1f05e1adadd_submission_2026-07-07T07_46_18.228Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
