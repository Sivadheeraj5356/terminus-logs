# A data platform must plan one overnight backup window. Jobs include snapshots, v

Submission: `dd7705eb-9118-46a8-8765-b0812d7ebbc4`  
Slug: `a-data-platform-must-plan-one-overnight-backup-window-jobs-i`  
Latest archive: `dd7705eb-9118-46a8-8765-b0812d7ebbc4_submission_2026-07-08T12_03_09.338Z.zip`  
Revisions in Dropbox: 4

## Task summary

A data platform must plan one overnight backup window. Jobs include snapshots, validations, compactions, and cross-region replications. Some jobs are mandatory, some are optional but improve restore coverage. Jobs form a dependency DAG and consume worker CPU, global network, and scratch storage over time. The jobs are in `/app/task_file/input_data/jobs.jsonl`; workers, capacities, dependencies, conflicts, and dataset freshness targets are in `/app/task_file/input_data/config.json`. Finish the skeleton Rust program in `/app/task_file/backupplanner/` so that, built with `cargo build --release` and run as `/app/task_file/backupplanner/target/release/backupplanner`, it reads the current input files at runtime and writes `/app/task_file/output_data/plan.json`. The binary must use those absolute task paths and work from any current working directory.

Required artifacts include: `/app/task_file/input_data/jobs.jsonl`, `/app/task_file/input_data/config.json`, `/app/task_file/backupplanner/`, `/app/task_file/backupplanner/target/release/backupplanner`, `/app/task_file/output_data/plan.json`, `/app/task_file/scripts/model.py`.

Author anonymous tagged this **hard** scientific-computing task (rust, optimization, scheduling, dag, resource-constrained, backup).

Time estimates: expert ~180 min, junior ~1200 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `dd7705eb-9118-46a8-8765-b0812d7ebbc4_submission_2026-07-08T12_03_09.338Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
