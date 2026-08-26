# Offline credit-model training is wrong on the graded folds. The offline feature

Submission: `303a8ae9-04ec-4794-a71e-0dcc7ce0bc3a`  
Slug: `offline-credit-model-training-is-wrong-on-the-graded-folds-t`  
Latest archive: `303a8ae9-04ec-4794-a71e-0dcc7ce0bc3a_submission_2026-07-18T09_55_23.670Z.zip`  
Revisions: 1

## Task summary

Offline credit-model training is wrong on the graded folds. The offline feature store materializes point-in-time training ledgers, then a small train and eval pass fits a model and scores holdout accuracy. Graded folds still feed bad feature state into those training batches. Repair is required in the Go source code under /app/environment. Library and CLI behavior must satisfy /app/environment/docs/n4_contract.md and the adjacent horizon and identity notes. Fold configs list feature_packs in replay order. The last put for a repeated revision id is authoritative. A kill frame revokes an existing revision. Compile with bash /app/environment/scripts/mk_all.sh, then regenerate /app/output/pit_report.json with /app/environment/bin/pitctl materialize --fold <id> --out /app/output/pit_report.json. Hand-written output JSON or a successful status command is insufficient.

Required artifacts include: `/app/environment`, `/app/environment/docs/n4_contract.md`, `/app/environment/scripts/mk_all.sh`, `/app/output/pit_report.json`, `/app/environment/bin/pitctl`, `/app/output/.pit_journal`, `/app/environment/trainkit/fit_eval.py`, `/app/output/train_metrics.json`.

Author anonymous tagged this **hard** machine-learning task (go, feature-store, training, model, leakage, dataset-split).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `303a8ae9-04ec-4794-a71e-0dcc7ce0bc3a_submission_2026-07-18T09_55_23.670Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
