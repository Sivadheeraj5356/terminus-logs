# Finance rejected /app/bin/commitment-chargeback. Totals discounts pool shares an

Submission: `7abf1f09-a031-4813-87a4-539f49cce12a`  
Slug: `finance-rejected-app-bin-commitment-chargeback-totals-discou`  
Latest archive: `7abf1f09-a031-4813-87a4-539f49cce12a_submission_2026-07-17T04_00_30.618Z.zip`  
Revisions: 5

## Task summary

Finance rejected /app/bin/commitment-chargeback. Totals discounts pool shares and report digest disagree and reruns are not byte identical. Edit only commitment.go ratecard.go intake.go and main.go under /app/carrydown_engine. Leave all other carrydown_engine files and leave /app/pledge_inputs and /app/billing_contracts byte identical write protected. Writes touch only /app/output/ledger.json. Rebuild with go build to /app/bin/commitment-chargeback as a Linux ELF using stdlib only. main.go keeps bare /app/pledge_inputs and /app/output constants. Delete Makefile json and C junk. Follow /app/billing_contracts/SCHEMA.md for all billing rules.

Required artifacts include: `/app/bin/commitment-chargeback`, `/app/carrydown_engine`, `/app/pledge_inputs`, `/app/billing_contracts`, `/app/output/ledger.json`, `/app/output`, `/app/billing_contracts/SCHEMA.md`.

Author anonymous tagged this **hard** data-processing task (chargeback, billing, commitment, carrydown, determinism, go).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `7abf1f09-a031-4813-87a4-539f49cce12a_submission_2026-07-17T04_00_30.618Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
