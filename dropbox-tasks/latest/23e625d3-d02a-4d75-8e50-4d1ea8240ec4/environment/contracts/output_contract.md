# Competing-risks modelling output specification

Write three files under `OUTPUT_PATH`. CSV files have one header row, comma
separators, no row names, and report every estimate as a finite decimal with at
least eight digits after the decimal point. All `cohort_summary.json` values are
plain integers.

Cause codes for the two-cause competing-risks model: **PCM** (progression) at
`ptime` when `pstat == 1`; **DEATH** (death without PCM) at `futime` when
`pstat == 0 & death == 1`; otherwise **censored** at `futime`. Let `E` be the
event time, `Y(u) = #{E >= u}` the number at risk just before `u`, `d_k(u)` the
cause-`k` count and `d(u)` the all-cause count. Everything below is computed on
the **active** patients unless stated otherwise.

## Disclosed preprocessing (used by `estimands.csv` and by prediction)

- Impute a blank `hgb`/`creat`/`mspike` with the active-patient median of that
  covariate.
- Standardize each continuous covariate `c` in {`age`,`hgb`,`creat`,`mspike`} as
  `c_z = (c - m_c) / s_c`, where `m_c` and `s_c` are the mean and the
  **population** standard deviation (divide by N, not N-1) over the active
  patients after imputation. `male = 1{sex == "M"}`. The covariate vector order
  is `[age_z, male, hgb_z, creat_z, mspike_z]`.

## `estimands.csv`

Columns `quantity,value`. Report exactly these rows (order is not graded):

**Marginal Aalen-Johansen cumulative incidence** `aj_cif_<cause>_<stratum>_<h>`
for cause in {`pcm`,`death`}, stratum in {`overall`,`age_low`,`age_high`}, and
both horizons `h`. `age_low` is `age <= age_cutpoint`, `age_high` is
`age > age_cutpoint`. Using `S(0)=1`, at each event time `u` (increasing)
`S(u) = S(u-) * (1 - d(u)/Y(u))` and
`CIF_k(t) = sum_{u<=t} S(u-) * d_k(u)/Y(u)`. (12 rows.)

**Reverse Kaplan-Meier median follow-up** `reverse_km_median`: Kaplan-Meier with
censoring as the event; the smallest event time `u` where that survival curve is
`<= 0.5`. (1 row.)

**Cause-specific Breslow Cox coefficients** `cox_pcm_beta_<cov>` and
`cox_death_beta_<cov>` for each covariate in `[age_z, male, hgb_z, creat_z,
mspike_z]` (10 rows). Fit a cause-specific Cox proportional-hazards model for
each cause (the competing cause treated as censoring) with **Breslow** tie
handling, by Newton-Raphson on the partial-likelihood score to convergence
(score magnitude below `1e-8`). Report the fitted coefficient of each covariate.

The selected prediction models and scales are reported separately in
`prediction_spec.csv`. The exact coefficient estimands in this file remain the
unshrunk full-cohort Breslow fits.

## `prediction_spec.csv`

Write exactly two rows with columns `cause,model,scale`, in `PCM` then `DEATH`
order. `cause` is one of those two strings, `model` is one of `core`,
`expanded`, or `full`, and `scale` is a finite decimal with at least eight
digits after the decimal point. The feature columns are:

- `core`: `age_z`, `male`, `creat_z`;
- `expanded`: `age_z`, `male`, `hgb_z`, `creat_z`;
- `full`: `age_z`, `male`, `hgb_z`, `creat_z`, `mspike_z`.

For each cause independently, evaluate every model/scale pair by deterministic
five-fold validation, with folds assigned by active-row position modulo five.
When evaluating a PCM candidate, use the full five-covariate death model at
scale `1.0`; when evaluating a DEATH candidate, use the full five-covariate PCM
model at scale `1.0`. Multiply only the candidate cause's coefficient vector
by its candidate scale. For each configured horizon, score only validation rows
whose horizon status is known (an event by the horizon or follow-up beyond it)
with the ordinary Brier score, then average across both horizons and folds.
Select the lowest mean score. A tie within `1e-12` first prefers scale `1.0`,
then model priority `full`, `expanded`, `core`. Refit the selected model and
scale for each cause on all active rows before predicting held-out patients.

## `predictions.csv`

Columns `row_id,horizon_month,pcm_prob`. For **every held-out patient** and
**each of the two horizons**, report `pcm_prob` = the predicted probability that
the patient progresses to PCM by that horizon given their covariates — i.e. the
covariate-conditional cumulative incidence of PCM, correctly accounting for the
competing risk of death. One row per (held-out `row_id`, horizon); the row count
equals `2 * n_heldout`.

These predictions are graded reference-relative against an independent
competing-risks model fit on the active patients. At each horizon the grader
checks a time-dependent Brier score (against a reference multiplier), a
cumulative/dynamic discrimination floor, and a calibration-in-the-large band,
plus anti-degeneracy checks. Predictors that ignore the competing risk of death
(e.g. a one-minus-Kaplan-Meier treating death as censoring) or that ignore the
covariates (one marginal number for everyone) do not pass.

The prediction rows must be produced using the two selected specifications
reported in `prediction_spec.csv`; the full unshrunk coefficients remain only
the exact estimands described above.

## `cohort_summary.json`

One flat JSON object with exactly these integer keys, over the **active**
patients: `n_active`, `n_heldout`, `n_pcm_active` (`pstat == 1`),
`n_death_active` (`pstat == 0 & death == 1`), `n_censored_active`
(`pstat == 0 & death == 0`), `n_male_active`, `n_female_active`.
