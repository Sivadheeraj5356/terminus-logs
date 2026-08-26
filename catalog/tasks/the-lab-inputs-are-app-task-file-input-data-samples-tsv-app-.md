# The lab inputs are `/app/task_file/input_data/samples.tsv`, `/app/task_file/inpu

Submission: `78665678-d231-4a75-80ae-c09a63b19387`  
Slug: `the-lab-inputs-are-app-task-file-input-data-samples-tsv-app-`  
Latest archive: `78665678-d231-4a75-80ae-c09a63b19387_submission_2026-07-04T08_30_38.764Z.zip`  
Revisions in Dropbox: 1

## Task summary

The lab inputs are `/app/task_file/input_data/samples.tsv`, `/app/task_file/input_data/panels.tsv`, and `/app/task_file/input_data/config.txt`. Build a native C optimizer at `/app/task_file/opt` from `/app/task_file/src/main.c`. Running it from `/app/task_file` must write `/app/task_file/output_data/batches.json`; it must also accept `/app/task_file/opt <input_dir> <output_dir>` and use those directories instead. The JSON shape is `{"panels":[{"panel_id":"A","sample_ids":["P01"]}],"runs":[{"lane":"L1","panel_ids":["A"]}]}`. Every mandatory sample is assigned exactly once, optional samples at most once, and a sample may only use a panel listing its family. Per-panel `reagent_a_cap`, `reagent_b_cap`, and `slot_cap` are hard limits. The plan must cover every `families=` value, meet `risk_floor=`, avoid `forbidden_pairs=`, separate cohorts when `cohort_separation=1`, spread `sentinel_families=` across at least `min_sentinel_panels=`, and complete at least `linked_pair_floor=` same-panel linked pairs. If either member of a linked pair is selected, both must be selected on the same panel.

Required artifacts include: `/app/task_file/input_data/samples.tsv`, `/app/task_file/input_data/panels.tsv`, `/app/task_file/input_data/config.txt`, `/app/task_file/opt`, `/app/task_file/src/main.c`, `/app/task_file`, `/app/task_file/output_data/batches.json`.

Author Vela tagged this **hard** scientific-computing task (c, optimization, pathogen, batching).

Time estimates: expert ~120 min, junior ~900 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `78665678-d231-4a75-80ae-c09a63b19387_submission_2026-07-04T08_30_38.764Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
