# Create the MiniZinc model `/app/task_file/models/shelter_staging.mzn`. The verif

Submission: `ba69b9ce-ce2e-442f-8c57-0418f46b0f0d`  
Slug: `create-the-minizinc-model-app-task-file-models-shelter-stagi`  
Latest archive: `ba69b9ce-ce2e-442f-8c57-0418f46b0f0d_submission_2026-07-15T05_55_20.978Z.zip`  
Revisions in Dropbox: 1

## Task summary

Create the MiniZinc model `/app/task_file/models/shelter_staging.mzn`. The verifier runs it with Gecode against public and additional compatible instances materialized from the schema below. Each instance supplies every field in `/app/task_file/instance_schema.json`: pallet count `P`, intake waves `W`, shelter zones `Z`, volunteer teams `T`, handling classes `H`, per-pallet `pallet_count`, `protection`, `mandatory`, `handling_class`, `arrival_minute`, `process_minutes`, and `deadline_minute`, zone/team eligibility matrices, wave/zone/team capacities, dependency parent indices, conflict-pair arrays, the scheduled-count band, minimum occupied wave/team cells, directed `class_changeover` minutes, per-class `class_min_waves`, and per-team `team_wave_limit`. Parent index zero means no dependency. The public instance is complete and follows the same contract as generated instances; do not add fallback values in the model.

Required artifacts include: `/app/task_file/models/shelter_staging.mzn`, `/app/task_file/instance_schema.json`.

Author anonymous tagged this **hard** scientific-computing task (emergency-management, constraint-programming, changeover-scheduling, minizinc).

Time estimates: expert ~260 min, junior ~1440 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `ba69b9ce-ce2e-442f-8c57-0418f46b0f0d_submission_2026-07-15T05_55_20.978Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
