# # Competing-risks progression modelling for a monoclonal-gammopathy cohort

Submission: `23e625d3-d02a-4d75-8e50-4d1ea8240ec4`  
Slug: `competing-risks-progression-modelling-for-a-monoclonal-gammo`  
Latest archive: `23e625d3-d02a-4d75-8e50-4d1ea8240ec4_submission_2026-07-19T13_25_46.997Z.zip`  
Revisions: 4

## Task summary

You are handed an event-history registry for a monoclonal-gammopathy (MGUS) cohort followed for progression to plasma-cell malignancy (PCM) and for death. PCM and death compete: a patient who dies first can never progress, so any analysis that treats death as ordinary censoring overstates PCM risk. The CSV is already a clean numerical registry — no cleaning, joining, or ETL is needed. Working in `/app`, write `/app/analysis.R` (base R only — no add-on survival package is installed) that reads `/app/data/registry.csv` and `/app/config/analysis.csv`, then writes three files under `OUTPUT_PATH` (default `/app/outputs`): `estimands.csv`, `prediction_spec.csv`, `predictions.csv`, and `cohort_summary.json`. Honor `DATA_PATH`, `CONFIG_PATH`, and `OUTPUT_PATH` overrides. Key requirements: Report a reduced block of exact estimators — marginal Aalen-Johansen; On the active patients, use deterministic five-fold validation at the two.

Required artifacts include: `/app/analysis.R`, `/app/data/registry.csv`, `/app/config/analysis.csv`, `/app/outputs`, `/app/contracts/output_contract.md`, `/app/contracts/data_dictionary.md`.

Author anonymous tagged this **hard** scientific-computing task (survival-analysis, competing-risks, cumulative-incidence, cause-specific-cox, risk-prediction).

Time estimates: expert ~210 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `23e625d3-d02a-4d75-8e50-4d1ea8240ec4_submission_2026-07-19T13_25_46.997Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
