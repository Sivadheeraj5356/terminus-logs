# Competing-risks progression modelling for a monoclonal-gammopathy cohort

You are handed an event-history registry for a monoclonal-gammopathy (MGUS)
cohort followed for progression to plasma-cell malignancy (PCM) and for death.
PCM and death compete: a patient who dies first can never progress, so any
analysis that treats death as ordinary censoring overstates PCM risk. The CSV is
already a clean numerical registry — no cleaning, joining, or ETL is needed.

Working in `/app`, write `/app/analysis.R` (base R only — no add-on survival
package is installed) that reads `/app/data/registry.csv` and
`/app/config/analysis.csv`, then writes three files under `OUTPUT_PATH` (default
`/app/outputs`): `estimands.csv`, `prediction_spec.csv`, `predictions.csv`,
and `cohort_summary.json`.
Honor `DATA_PATH`, `CONFIG_PATH`, and `OUTPUT_PATH` overrides.

Two obligations, both fit on the **active** (fully labelled) patients only:

1. Report a reduced block of exact estimators — marginal Aalen-Johansen
   cumulative incidence for PCM and death by age stratum, reverse-Kaplan-Meier
   median follow-up, and the cause-specific Breslow Cox coefficients for both
   causes — plus the active-cohort counts.
2. On the active patients, use deterministic five-fold validation at the two
configured horizons to choose a prediction specification separately for each
cause. A specification is one feature family and one coefficient scale. The
feature families are `core = [age_z, male, creat_z]`,
`expanded = [age_z, male, hgb_z, creat_z]`, and
`full = [age_z, male, hgb_z, creat_z, mspike_z]`; the candidate scales are
`{0.75, 0.9, 1.0, 1.1, 1.25}`. For a PCM candidate, fit that candidate PCM
model while fitting the death model on all five covariates at scale `1.0`; for
a death candidate, reverse those roles. Score every candidate by its
two-horizon mean Brier score, averaged over the five folds. Select the lowest
score; on a tie within `1e-12`, prefer scale `1.0`, then model priority `full`,
`expanded`, `core`. Fit the selected cause-specific models on all active
patients and, for every **held-out** patient (the rows whose outcome columns
are blank), predict PCM incidence by each configured horizon, correctly
accounting for death as the competing risk.

Report the selected PCM and death feature families and scales in
`prediction_spec.csv`. The predictions are graded against an independent reference model on Brier
score, discrimination, and calibration; predictors that ignore the competing
risk or ignore covariates will not pass. See
`/app/contracts/output_contract.md` for the exact preprocessing rules, keys,
schemas, and `/app/contracts/data_dictionary.md` for the columns and the
active/held-out convention. The analysis must be deterministic and rerunnable.
This is a scientific survival-modeling task: the graded work is competing-risk estimation and calibrated risk prediction, not ETL or data-processing.
