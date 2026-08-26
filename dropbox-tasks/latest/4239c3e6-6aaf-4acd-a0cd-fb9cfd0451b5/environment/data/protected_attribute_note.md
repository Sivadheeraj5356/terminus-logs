# Protected attribute: education

education is a protected attribute and must not enter the model as an input,
directly or through a one-to-one recoding of it. This is a disparate-treatment
(anti-classification) prohibition: the score for a contact must not change if only
its education label is changed. The verifier reruns your script on a variant in
which the education column has been permuted across rows, and your predictions and
metrics must be byte-for-byte unchanged.

Every other column may be used, including columns correlated with education such as
job, age and contact channel. The task is to recover the subscription signal for
every education group through these mediating covariates and to keep the scores
calibrated and discriminating within each group without looking at education.
