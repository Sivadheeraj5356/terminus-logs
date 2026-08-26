# Lab cooling spreadsheets disagree with thermal exports when normalization, maski

- **UUID:** `698695cd-8cb4-46e0-88d5-c06c44745da9`
- **Slug:** `lab-cooling-spreadsheets-disagree-with-thermal-exports-when`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Lab cooling spreadsheets disagree with thermal exports when normalization, masking, and curve-fitting steps from the operator runbook are skipped. Repair the Go project under `/app` so the CLI emits deterministic calibration artifacts that follow the documented scientific procedure.

Build with `go build -o /app/bin/thermalcal /app/cmd/thermalcal`. With no arguments, consume `/app/input_data` and write a top-level calibration report at `/app/output_data/calibration_report.json` plus `/app/output_data/intermediate/frame_summaries.jsonl` and `/app/output_data/intermediate/session_fits.jsonl`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
