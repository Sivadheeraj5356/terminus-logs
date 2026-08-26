# Fabert is a ChaLearn wide-table multiclass dataset with 800 numeric features and

Submission: `f5e0f8cb-40da-4dfb-81fe-891f2a26cb15`  
Slug: `fabert-is-a-chalearn-wide-table-multiclass-dataset-with-800-`  
Latest archive: `f5e0f8cb-40da-4dfb-81fe-891f2a26cb15_submission_2026-07-12T20_07_33.198Z.zip`  
Revisions in Dropbox: 4

## Task summary

Fabert is a ChaLearn wide-table multiclass dataset with 800 numeric features and labels 0 through 6. Update /app/analysis.R in place so a clean run reads labelled training rows from DATA_DIR/fabert_train.csv, default DATA_DIR=/app/data, scores unlabelled rows from DATA_DIR/fabert_score.csv, and recreates every deliverable under OUT_DIR, default /app/outputs. Use the provided row_id column as the stable source row id and class order 0,1,2,3,4,5,6. Produce scored predictions, class probabilities, and a class-weight audit. The scoring file intentionally has no labels, so do not fabricate or output true labels. The verifier will compute macro_f1 >= 0.58, balanced_accuracy >= 0.60, log_loss <= 1.28, top3_accuracy >= 0.88, weighted_calibration_error <= 0.20, class 0 recall >= 0.44, and class 6 recall >= 0.70 from held-out truth. Use inverse-frequency class weights from training rows only: total_training_rows / (7 * training_count_for_label). Each training row's model weight is the weight for its original class. Report random_seed 20260707.

Required artifacts include: `/app/analysis.R`, `/app/data`, `/app/outputs`.

Author anonymous tagged this **hard** machine-learning task (crucible, r, openml, fabert, metric-mismatch, multi-class).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `f5e0f8cb-40da-4dfb-81fe-891f2a26cb15_submission_2026-07-12T20_07_33.198Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
