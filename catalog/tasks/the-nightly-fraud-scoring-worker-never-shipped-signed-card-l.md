# The nightly fraud scoring worker never shipped — signed card-ledger batches are 

Submission: `7eed578d-bc0f-4fec-9159-45f76fd558e1`  
Slug: `the-nightly-fraud-scoring-worker-never-shipped-signed-card-l`  
Latest archive: `7eed578d-bc0f-4fec-9159-45f76fd558e1_submission_2026-07-06T09_06_41.491Z.zip`  
Revisions in Dropbox: 1

## Task summary

The nightly fraud scoring worker never shipped — signed card-ledger batches are sitting unverified and job `JOB-20250620-001` is stuck queued in `/var/lib/ops/ops.db`. Ops wants a C worker built under `/app` (Makefile + `risk_worker` binary) per `/app/data/policy/risk_policy_manual.txt`. Place all `.c` and `.h` source files and the Makefile directly under `/app/` in a flat layout — subdirectories such as `/app/src/` are not accepted by the build artifact checks. Milestone 1 is ledger provenance only: implement `verify-ledger` on `/app/risk_worker` per the policy manual. Do not touch feature or scoring tables yet.

Required artifacts include: `/app/data/policy/risk_policy_manual.txt`, `/app/src/`, `/app/risk_worker`.

Author anonymous tagged this **medium** security task (openssl, sqlite, fraud-scoring, hmac, logistic-regression).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7eed578d-bc0f-4fec-9159-45f76fd558e1_submission_2026-07-06T09_06_41.491Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
