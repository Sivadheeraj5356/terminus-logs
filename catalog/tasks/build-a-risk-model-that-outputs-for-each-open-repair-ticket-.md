# Build a risk model that outputs, for each open repair ticket, a calibrated proba

Submission: `2b5592e0-14a5-4aa7-998b-2e19833eb246`  
Slug: `build-a-risk-model-that-outputs-for-each-open-repair-ticket-`  
Latest archive: `2b5592e0-14a5-4aa7-998b-2e19833eb246_submission_2026-07-19T11_45_20.407Z.zip`  
Revisions in Dropbox: 3

## Task summary

Build a risk model that outputs, for each open repair ticket, a calibrated probability it needs a repeat truck-roll within thirty days and whether to assign a senior technician now. You inherit a pipeline at /app/analysis.R whose validation looks strong but does not generalize to the open tickets; diagnose why and make them trustworthy. The data is /app/data/service_ledger.csv; schema in /app/contracts/schema.md, artifacts in /app/contracts/output_contract.md. Each row is one ticket. repeat_visit is 1 if it needed a repeat truck-roll, 0 if resolved first time, blank for the open tickets in the newest service_month, which you must score and which sit a few months past the last labeled month. Repeat rates rise across service_month and decelerate; the flattening shows only across the full labeled history, not the recent window, and the job_complexity effect differs by equipment_class, so fit the whole history and keep the probabilities calibrated within every equipment_class across the job_complexity range. Missing a repeat costs about five times a needless senior dispatch, so pick the cost-minimizing threshold, not the half. One field settles only once the outcome is known yet carries a provisional value on open tickets, so it must not drive the model whatever its name; leaning on it scores well then collapses on the open batch. The newest month adds an equipment_class with no history, needing a fallback that scores it calibrated to its own repeat rate, not merely ranked. Fit on the genuine ticket cohort only: a few tickets appear more than once, prior_tickets_90d uses -1...

Required artifacts include: `/app/analysis.R`, `/app/data/service_ledger.csv`, `/app/contracts/schema.md`, `/app/contracts/output_contract.md`, `/app/outputs`.

Author anonymous tagged this **hard** machine-learning task (classification, calibration, data-leakage, concept-drift, cold-start, cost-sensitive).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `2b5592e0-14a5-4aa7-998b-2e19833eb246_submission_2026-07-19T11_45_20.407Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
