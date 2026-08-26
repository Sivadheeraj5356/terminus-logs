# cloglog_model.json

Written to /app/outputs/cloglog_model.json as a single JSON object with exactly these keys:

- n_obs: int, the number of runs
- n_events: int, the number of failure events
- coefficients: object keyed by term name, with the key "(Intercept)" and one key per predictor, each value an object with:
  - estimate: float, the fitted coefficient, rounded to 6 decimals
  - std_error: float, the standard error of the coefficient, rounded to 6 decimals
  - z_value: float, the Wald statistic estimate divided by standard error, rounded to 6 decimals
  - p_value: float, the two-sided normal p-value for that Wald statistic, rounded to 8 decimals
- null_deviance: float, the deviance of the intercept-only model, rounded to 4 decimals
- deviance: float, the residual deviance of the fitted model, rounded to 4 decimals
- aic: float, the AIC of the fitted model, rounded to 4 decimals
- lr_statistic: float, the likelihood-ratio statistic comparing the fitted model with the intercept-only null (the null deviance minus the residual deviance), rounded to 4 decimals
- lr_df: int, the degrees of freedom of that likelihood-ratio test, equal to the number of predictors
- lr_pvalue: float, the upper-tail chi-squared p-value of the likelihood-ratio statistic, rounded to 8 decimals
- average_marginal_effects: object keyed by predictor name (no intercept), each value the predictor's average marginal effect on the failure probability, rounded to 8 decimals
- permutation_test: object, the permutation assessment of the largest predictor effect, with:
  - n_permutations: int, the number of reorderings used, equal to the number of rows in permutation_index.csv
  - observed_max_abs_coef: float, the largest absolute value among the eighteen fitted predictor coefficients (the intercept is excluded), rounded to 6 decimals
  - null_q95_max_abs_coef: float, the 95th percentile of the permutation null distribution defined below, rounded to 6 decimals

## Definitions

The average marginal effect of a predictor is the sample mean, over all runs, of the partial derivative of the modelled failure probability with respect to that predictor. Under the complementary log-log link the failure probability is one minus the exponential of minus the exponential of the linear predictor, so the derivative for a predictor is its coefficient times the exponential of (the linear predictor minus the exponential of the linear predictor), averaged over the runs.

## Pinned definition of the permutation test

/app/data/permutation_index.csv has one row per reordering and one column per run, each row a permutation of the run indices 1..n. For each reordering, apply it to the failure outcome (leaving the eighteen predictors in place), refit the same complementary log-log model, and record the largest absolute value among the eighteen predictor coefficients of that refit (excluding the intercept). The collection of those values across all reorderings is the permutation null distribution. Report:

- observed_max_abs_coef: the same quantity for the real fit (the largest absolute predictor coefficient of the model fitted on the actual outcome)
- null_q95_max_abs_coef: the 95th percentile (linear interpolation, the type-7 definition used by both R quantile and numpy percentile) of the null distribution

The null 95th percentile has no closed-form shortcut: it can only be obtained by running the refits. Reporting an asymptotic critical value, refitting without permuting the outcome, or permuting the predictors instead of the outcome all disagree with the recomputation.

## Grading

Grading recomputes every quantity from the raw design with an independent maximum-likelihood fit and compares: each coefficient within a near-separation tolerance, each standard error within 0.05, each Wald z within 0.1 and each Wald p within 0.001; the null deviance, residual deviance and AIC each within 0.1; the likelihood-ratio statistic within 0.1, its degrees of freedom exactly, and its p-value within 0.001; each average marginal effect within 0.0005; the fitted probabilities within 0.02; and, for the permutation test, the permutation count exactly, observed_max_abs_coef within 0.05, and null_q95_max_abs_coef within 0.1.
