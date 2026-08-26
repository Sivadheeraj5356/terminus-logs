# Model-risk evaluation notes

This workspace hosts a conformal-prediction readiness evaluator for pharmacy
ops uncertainty briefs.

Primary ML activities:
- apply frozen calibration annexes (`data/cal/`) when forming segment totals
- score coverage-related gate rows under training vs held-out board pairs
- stress adversarial generalization on opaque xp pair packs (`data/xp/`)
- keep rollback metric-family lineage aligned with the winning calibration sheet

Public packing rules: `docs/seal_k4.md`.
Rebuild entrypoint: `scripts/run_k4.sh`.
Desk observables: `tools/obs_k4`.
