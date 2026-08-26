Offline credit-model training is wrong on the graded folds. The offline feature
store materializes point-in-time training ledgers, then a small train and eval
pass fits a model and scores holdout accuracy. Graded folds still feed bad
feature state into those training batches.

Repair is required in the Go source code under /app/environment. Library and
CLI behavior must satisfy /app/environment/docs/n4_contract.md and the adjacent
horizon and identity notes. Fold configs list feature_packs in replay order.
The last put for a repeated revision id is authoritative. A kill frame revokes
an existing revision. Compile with bash
/app/environment/scripts/mk_all.sh, then regenerate /app/output/pit_report.json with
/app/environment/bin/pitctl materialize --fold <id> --out
/app/output/pit_report.json. Hand-written output JSON or a successful status
command is insufficient.

The report carries fold_id, rows, audit_trace, and ledger_digest. Its journal
under /app/output/.pit_journal carries seg_digests that agree with the report.
Use /app/environment/bin/pitctl verify --fold <id> --report
/app/output/pit_report.json to check the pair. Score the regenerated report with
python3 /app/environment/trainkit/fit_eval.py --report
/app/output/pit_report.json --out /app/output/train_metrics.json. As documented
in /app/environment/docs/train_loop.md, fit_eval reports train_metrics.
train_rows means the number of earlier temporal-partition rows, holdout_rows
means the number of later rows, and holdout_accuracy is computed on that later
partition. leakage_hits counts policy violations, and training_ok reports
whether training completed without leakage.
