Deployment-calibrated, education-fair term-deposit scoring

The file /app/environment/data/bank_additional.csv holds client-contact records from
a bank's term-deposit campaign (UCI Bank Marketing): a stable row_id key, client and
campaign attributes, five macroeconomic covariates, and y, whether the client
subscribed. Rows with a present y are training data; rows with a blank y are the
held-out deployment contacts to score. The data notes describe the split and
constraints.

The training rows are a case-control sample: subscribers were kept and
non-subscribers down-sampled, so the training subscription rate is about one half,
far above the true live rate. Down-sampling was random within each class, so only the
subscribe mix differs between training and deployment; within a class the feature
distribution is unchanged. There is no sampling-weight column and the deployment rate
is not given: recover it from the unlabelled held-out contacts and reconcile your
scores onto it, or they read far too high.

This is also a fairness task. education is a protected attribute and must not be a
model input, directly or through any one-to-one recoding of it; the verifier reruns
your script with only the education column permuted and your predictions must be
unchanged. The scores are graded on ranking and, within every education group, on
Brier and calibration to that group's true deployment rate, plus a disparity
certificate over the groups, all against an unaware reference. A model left at the
enriched training rate is badly miscalibrated within every group and fails.

Work offline in R at /app/environment/analysis.R, writing
/app/environment/outputs/predictions.csv and metrics.json per
/app/environment/contracts/output_contract.md.
