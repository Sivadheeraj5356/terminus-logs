# The directory /app holds a small offline data-processing tool that turns haul-pe

Submission: `a460ca27-bf77-4620-860d-a4b6b68313bf`  
Slug: `the-directory-app-holds-a-small-offline-data-processing-tool`  
Latest archive: `a460ca27-bf77-4620-860d-a4b6b68313bf_submission_2026-07-07T09_40_33.983Z.zip`  
Revisions in Dropbox: 1

## Task summary

The directory /app holds a small offline data-processing tool that turns haul-permit telemetry into a billing-style ledger report. It ingests two structured text files (a quarry-config and a traffic-event stream) and replays the stream against the configured allowances to produce a deterministic ledger, one record per line on standard output. Run it as:

Required artifacts include: `/app/report.py`, `/app/docs/spec.md`.

Author anonymous tagged this **hard** data-processing task (mining, logistics, capacity, allocation).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a460ca27-bf77-4620-860d-a4b6b68313bf_submission_2026-07-07T09_40_33.983Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
