# The lab inputs are `/app/task_file/input_data/samples.tsv`, `/app/task_file/inpu

- **UUID:** `78665678-d231-4a75-80ae-c09a63b19387`
- **Slug:** `the-lab-inputs-are-app-task-file-input-data-samples-tsv-app`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The lab inputs are `/app/task_file/input_data/samples.tsv`, `/app/task_file/input_data/panels.tsv`, and `/app/task_file/input_data/config.txt`. Build a native C optimizer at `/app/task_file/opt` from `/app/task_file/src/main.c`.

Running it from `/app/task_file` must write `/app/task_file/output_data/batches.json`; it must also accept `/app/task_file/opt <input_dir> <output_dir>` and use those directories instead. The JSON shape is `{"panels":[{"panel_id":"A","sample_ids":["P01"]}],"runs":[{"lane":"L1","panel_ids":["A"]}]}`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
