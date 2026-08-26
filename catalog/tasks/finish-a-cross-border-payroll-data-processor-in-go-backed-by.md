# Finish a cross-border payroll data processor in Go, backed by SQLite. A scaffold

Submission: `6023158a-6fd3-4f0f-aec7-8b224e0004c7`  
Slug: `finish-a-cross-border-payroll-data-processor-in-go-backed-by`  
Latest archive: `6023158a-6fd3-4f0f-aec7-8b224e0004c7_submission_2026-07-20T22_14_24.567Z.zip`  
Revisions in Dropbox: 5

## Task summary

Finish a cross-border payroll data processor in Go, backed by SQLite. A scaffold is waiting in /app: command wiring, SQLite plumbing, the statutory schedule tables, and the country-metadata loader are already there. Nine pieces are stubbed out: employee/hours storage, progressive withholding, a currency-to-minor-unit mapping, a continent-to-region mapping, social contribution, a two-leg currency conversion, employee-country assignment, a country cost ranking, and a ceiling on total social spend per report run. Build with go build -o /app/crosspay .; offline, standard-library only. Every amount is an integer number of micro-units of a major currency, every rate an integer basis-point count, no floating point anywhere. Gross pay is hours times rate; withholding runs the progressive statutory tiers for a region; net pay is gross minus withholding. Cross-border commands read a country's currency and continent from the dataset and report figures in that currency's own minor unit. Social contribution is charged on a base clamped between a per-country floor and a per-region cap, at the region's rate. Local amounts reach base currency only through a pivot currency, each leg rounded independently. Employees can be assigned to countries, and a report ranks countries by employer cost with a multi-key tie-break; when combined social spend crosses an institutional ceiling, each country's share is apportioned back down first.

Required artifacts include: `/app/crosspay`, `/app/docs/spec.md`.

Author anonymous tagged this **hard** data-processing task (go, sqlite, payroll, currency, iso4217, ranking, dataset).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `6023158a-6fd3-4f0f-aec7-8b224e0004c7_submission_2026-07-20T22_14_24.567Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
