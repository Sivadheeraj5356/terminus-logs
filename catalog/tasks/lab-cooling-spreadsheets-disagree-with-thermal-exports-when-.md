# Lab cooling spreadsheets disagree with thermal exports when normalization, maski

Submission: `698695cd-8cb4-46e0-88d5-c06c44745da9`  
Slug: `lab-cooling-spreadsheets-disagree-with-thermal-exports-when-`  
Latest archive: `698695cd-8cb4-46e0-88d5-c06c44745da9_submission_2026-07-13T18_32_44.288Z.zip`  
Revisions in Dropbox: 1

## Task summary

Lab cooling spreadsheets disagree with thermal exports when normalization, masking, and curve-fitting steps from the operator runbook are skipped. Repair the Go project under `/app` so the CLI emits deterministic calibration artifacts that follow the documented scientific procedure. Build with `go build -o /app/bin/thermalcal /app/cmd/thermalcal`. With no arguments, consume `/app/input_data` and write a top-level calibration report at `/app/output_data/calibration_report.json` plus `/app/output_data/intermediate/frame_summaries.jsonl` and `/app/output_data/intermediate/session_fits.jsonl`. With two arguments, treat them as input and output directories and create the full output tree, including nested intermediate folders such as `/app/output_data/nested/deep/out/intermediate`.

Required artifacts include: `/app/bin/thermalcal`, `/app/cmd/thermalcal`, `/app/input_data`, `/app/output_data/calibration_report.json`, `/app/output_data/intermediate/frame_summaries.jsonl`, `/app/output_data/intermediate/session_fits.jsonl`, `/app/output_data/nested/deep/out/intermediate`, `/app/docs/calibration_runbook.md`.

Author anonymous tagged this **hard** scientific-computing task (go, scientific-computing, image-processing, radiometry, terraform, curve-fitting).

Time estimates: expert ~120 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `698695cd-8cb4-46e0-88d5-c06c44745da9_submission_2026-07-13T18_32_44.288Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
