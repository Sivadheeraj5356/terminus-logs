# Retention coordinate model

The small model is intended for cross-run QC, not peptide identification.
Coordinates remove run-specific positive affine drift before peptide centers
are estimated. Leave-one-run-out records make the provenance of every center
auditable and prevent a run from calibrating its own residuals.

The finite-sample threshold is deliberately reported with its integer rank.
Consumers should use the recorded residual rows for accounting rather than
interpreting coverage as a population guarantee.
