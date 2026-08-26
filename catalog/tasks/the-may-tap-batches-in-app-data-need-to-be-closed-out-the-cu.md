# The May tap batches in /app/data need to be closed out. The current /app/reconci

Submission: `b6180f8d-3fd8-4c68-81ce-56c25093807f`  
Slug: `the-may-tap-batches-in-app-data-need-to-be-closed-out-the-cu`  
Latest archive: `b6180f8d-3fd8-4c68-81ce-56c25093807f_submission_2026-07-15T20_03_34.178Z.zip`  
Revisions in Dropbox: 4

## Task summary

The May tap batches in /app/data need to be closed out. The current /app/reconcile.js is just a placeholder, so replace it with Node.js code that runs with `node /app/reconcile.js` using only the files and packages already present in the image. Read the JSONL and CSV feeds, the late tap-correction feed, the temporary service-zone adjustment feed, the subsidy recovery feed, the settlement hold feed, the carry-forward credit feed, the credit reversal feed, the route-family minimum feed, the cap-exclusion feed, the account link feed, the account credit feed, /app/contracts/fare_policy.sqlite, and /app/docs/fare-policy.md. Do not change any raw input files or the policy database.

Required artifacts include: `/app/data`, `/app/reconcile.js`, `/app/contracts/fare_policy.sqlite`, `/app/docs/fare-policy.md`, `/app/data/zone-adjustments/`, `/app/data/holds/`, `/app/data/carryovers/`, `/app/data/credit-reversals/`.

Author anonymous tagged this **medium** data-processing task (sqlite, csv, jsonl, fare-reconciliation, carryover-credits, account-credits).

Time estimates: expert ~210 min, junior ~420 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `b6180f8d-3fd8-4c68-81ce-56c25093807f_submission_2026-07-15T20_03_34.178Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
