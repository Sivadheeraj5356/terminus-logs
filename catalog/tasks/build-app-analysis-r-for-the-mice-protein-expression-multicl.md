# Build /app/analysis.R for the Mice Protein Expression multiclass task. Read /app

Submission: `21468c19-07d6-4a49-9133-90813ea846c9`  
Slug: `build-app-analysis-r-for-the-mice-protein-expression-multicl`  
Latest archive: `21468c19-07d6-4a49-9133-90813ea846c9_submission_2026-07-16T17_09_56.918Z.zip`  
Revisions: 6

## Task summary

Build /app/analysis.R for the Mice Protein Expression multiclass task. Read /app/data/train.csv and /app/config/model_config.json, preserve the supplied fit, validation, and test roles, and learn every preprocessing choice from fit rows only. Use the closed-form one-vs-rest ridge score model described in /app/docs/07_model.txt, with softmax probabilities in the configured class order. Keep test labels out of model choice, preprocessing, lambda selection, and stability or refit decisions. Write /app/outputs/metrics.json, /app/outputs/predictions.csv, /app/outputs/class_report.csv, /app/outputs/confusion_matrix.csv, /app/outputs/missing_report.csv, /app/outputs/validation_report.csv, /app/outputs/stability_refit_predictions.csv, /app/outputs/stability_refit_report.csv, /app/outputs/robust_lambda_consensus_report.csv, /app/outputs/feature_drop_refit_report.csv, /app/outputs/protein_pair_drop_refit_report.csv, /app/outputs/boundary_refit_report.csv, /app/outputs/paired_boundary_reselection_report.csv, and /app/outputs/model_manifest.json. Predictions are for test rows only and stay in row_id order. Treat blanks, literal question marks, and nan style markers as missing before numeric imputation or categorical level handling. Exact schemas, ordering, missing-value format, and manifest literals are in /app/docs/19_schema.txt.

Required artifacts include: `/app/analysis.R`, `/app/data/train.csv`, `/app/config/model_config.json`, `/app/docs/07_model.txt`, `/app/outputs/metrics.json`, `/app/outputs/predictions.csv`, `/app/outputs/class_report.csv`, `/app/outputs/confusion_matrix.csv`.

Author anonymous tagged this **hard** machine-learning task (classification, biology, tabular, missing-values, multi-class).

Time estimates: expert ~145 min, junior ~370 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `21468c19-07d6-4a49-9133-90813ea846c9_submission_2026-07-16T17_09_56.918Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
