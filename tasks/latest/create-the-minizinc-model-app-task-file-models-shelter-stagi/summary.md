# Create the MiniZinc model `/app/task_file/models/shelter_staging.mzn`. The verif

- **UUID:** `ba69b9ce-ce2e-442f-8c57-0418f46b0f0d`
- **Slug:** `create-the-minizinc-model-app-task-file-models-shelter-stagi`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Create the MiniZinc model `/app/task_file/models/shelter_staging.mzn`. The verifier runs it with Gecode against public and additional compatible instances materialized from the schema below.

Each instance supplies every field in `/app/task_file/instance_schema.json`: pallet count `P`, intake waves `W`, shelter zones `Z`, volunteer teams `T`, handling classes `H`, per-pallet `pallet_count`, `protection`, `mandatory`, `handling_class`, `arrival_minute`, `process_minutes`, and `deadline_minute`, zone/team eligibility matrices, wave/zone/team capacities, dependency parent indices, conflict-pair arrays, the scheduled-count band, minimum occupied wave/team cells, directed `class_changeover` minutes, per-class `class_min_waves`, and per-team `team_wave_limit`. Parent index zero means no dependency.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
