# Evaluate the supplied conformal predictor in `/app/environment` across the four

- **UUID:** `f9831bda-e411-410b-9daa-046e8a4504f7`
- **Slug:** `evaluate-the-supplied-conformal-predictor-in-app-environment`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Evaluate the supplied conformal predictor in `/app/environment` across the four calibration profiles and all four pass modes. The evaluation must write a deterministic sixteen-cycle report to `/app/output/cp_witness.json` with the coverage and nonconformity-score consistency defined in `/app/environment/docs/cp_contract.md`.

Use the existing Go evaluator and calibration fixtures. Build it with `bash /app/environment/scripts/rebuild_bins.sh`, run the evaluation with `bash /app/environment/scripts/drive_matrix.sh`, and validate the report with `/app/bin/cp_audit --coverage-audit --out /app/output/cp_witness.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
