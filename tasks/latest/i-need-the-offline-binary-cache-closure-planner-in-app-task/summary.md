# I need the offline binary-cache closure planner in `/app/task_file` turned into

- **UUID:** `17e616cc-325e-459c-a30f-5ad51f4c1b8a`
- **Slug:** `i-need-the-offline-binary-cache-closure-planner-in-app-task`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

I need the offline binary-cache closure planner in `/app/task_file` turned into a real native Go CLI. Build `/app/bin/closure-plan` from `/app/task_file/src` and make it run as `/app/bin/closure-plan CASE_ROOT OUTDIR`; the case format, trust rules, closure rules, selection tuple, and exact output schemas are in `/app/task_file/CLOSURE_PLAN_CONTRACT.txt`, with the public case at `/app/task_file/cases/public`.

For each run, replace the output directory contents and write exactly `/app/out/closure.json`, `/app/out/actions.tsv`, and `/app/out/proof.json` when invoked as `/app/bin/closure-plan /app/task_file/cases/public /app/out`. The binary must print nothing to stdout and must work for the public case, every case under `/app/task_file/cases/samples`, copied roots, stale-output reruns, and hidden compatible cases that follow the same documented contract.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
