# Model evaluation role

This tool is part of a model-evaluation pipeline for confidence calibration.

What the tool does

1. Fit post-hoc calibrators (histogram binning, isotonic regression, grouped
   isotonic regression) on held-out fit-fold predictions from a trained
   classifier.
2. Measure expected calibration error on distribution-shift evaluation rungs
   using equal-mass reliability bins.
3. Select a calibration family per shift severity under ECE budgets,
   nondecreasing strength, and per-rung strength-span limits.
4. Emit calibrated confidences, per-rung ECE figures, and a holdout-fold
   sealed-edge ECE witness for every calibration family.

Normative arithmetic is in `/app/environment/docs/contract.rst`. Durable
evaluation-state layout (sealed reliability edges and interrupted-run resume)
is in `/app/environment/docs/protocol.rst`. Those pages support repeatable model
evaluation; they are not a generic application-storage feature.
