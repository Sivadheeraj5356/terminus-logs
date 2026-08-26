# The shipped Go equivalence service audits twenty cross compilation build session

Submission: `887c1838-7921-488f-9548-370711c061ef`  
Slug: `the-shipped-go-equivalence-service-audits-twenty-cross-compi`  
Latest archive: `887c1838-7921-488f-9548-370711c061ef_submission_2026-07-19T17_29_15.395Z (2).zip`  
Revisions: 5

## Task summary

The shipped Go equivalence service audits twenty cross compilation build sessions under /app/build-sessions named build_01.json through build_20.json. Each session records toolchain artifacts, compilation checkpoints, ordered stage events, rollback attempts, distributed shard merges, and optimization pass fingerprints. Implement EvaluateSession in /app/equivalence-engine/evaluate.go without changing toolchain-cli/main.go or report-writer/emit.go. Run make build from /app until /app/bin/artifact-equivalence-checker exceeds 2048 bytes. Do not run go fmt or goimports on files outside equivalence-engine. Write /app/output/equivalence_report.json per /app/contracts/OUTPUT_SCHEMA.md and /app/references/session_format.md.

Required artifacts include: `/app/build-sessions`, `/app/equivalence-engine/evaluate.go`, `/app/bin/artifact-equivalence-checker`, `/app/output/equivalence_report.json`, `/app/contracts/OUTPUT_SCHEMA.md`, `/app/references/session_format.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (cross-compilation, build-systems, artifact-equivalence, go, determinism).

Time estimates: expert ~120 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `887c1838-7921-488f-9548-370711c061ef_submission_2026-07-19T17_29_15.395Z (2).zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. This latest zip contains result.json/reward.txt — see extracted files.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
