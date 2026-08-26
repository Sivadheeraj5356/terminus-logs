Calibrated purchase-probability estimation under a seasonal distribution shift

This is a supervised machine-learning task: train a probabilistic classifier on
labeled browsing sessions and use it to predict calibrated purchase probabilities
for unlabeled sessions that come from a different, shifted distribution. It is a
domain-adaptation and probability-calibration problem, not a lookup or aggregation.

The labeled training sessions (the off-season "source" regime) and the sessions
you must score (the peak-season "target" regime) come from different
distributions; purchase behaviour differs between the regimes. Every source
session is labeled. In the target regime only a small labeled pilot is provided;
the remaining target sessions have a blank outcome and are the ones you must
score.

The dataset at /app/environment/data/online_shoppers.csv holds 12330 e-commerce
sessions: a stable row_id, ten numeric engagement features, six categorical
context features, a domain indicator, and a binary purchase outcome. The data
directory's notes and summaries document the columns and the split; derive any
distributional quantities you need from the data itself.

Your predictions are graded on both discrimination and calibration, within
engagement bands and overall, against withheld outcomes and a reference model
refit on the active data. The verifier re-fits and re-scores on several
deterministically perturbed resamples of the data, so every reported quantity
must be derived from the data you read, never hardcoded.

Train your model and write the predictions in R at /app/environment/analysis.R,
reporting the per-session probabilities and the summary statistics exactly as
specified in /app/environment/contracts/output_contract.md (run with Rscript
/app/environment/analysis.R).
