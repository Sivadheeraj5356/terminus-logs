# I need the offline binary-cache closure planner in `/app/task_file` turned into 

Submission: `17e616cc-325e-459c-a30f-5ad51f4c1b8a`  
Slug: `i-need-the-offline-binary-cache-closure-planner-in-app-task`  
Latest archive: `17e616cc-325e-459c-a30f-5ad51f4c1b8a_submission_2026-07-15T15_24_07.597Z.zip`  
Revisions: 2

## Task summary

I need the offline binary-cache closure planner in `/app/task_file` turned into a real native Go CLI. Build `/app/bin/closure-plan` from `/app/task_file/src` and make it run as `/app/bin/closure-plan CASE_ROOT OUTDIR`; the case format, trust rules, closure rules, selection tuple, and exact output schemas are in `/app/task_file/CLOSURE_PLAN_CONTRACT.txt`, with the public case at `/app/task_file/cases/public`. For each run, replace the output directory contents and write exactly `/app/out/closure.json`, `/app/out/actions.tsv`, and `/app/out/proof.json` when invoked as `/app/bin/closure-plan /app/task_file/cases/public /app/out`. The binary must print nothing to stdout and must work for the public case, every case under `/app/task_file/cases/samples`, copied roots, stale-output reruns, and hidden compatible cases that follow the same documented contract.

Required artifacts include: `/app/task_file`, `/app/bin/closure-plan`, `/app/task_file/src`, `/app/task_file/CLOSURE_PLAN_CONTRACT.txt`, `/app/task_file/cases/public`, `/app/out/closure.json`, `/app/out/actions.tsv`, `/app/out/proof.json`.

Author Anonymous tagged this **hard** build-and-dependency-management task (go, native-binary, nix, binary-cache, closure-planning, offline-build).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Harbor trials: 1 — 1 solved, 0 valid fail, 0 timeout, 0 infra.

## Agent summary

Skipping image OS validation for hb__35d60909a0e5dddeb6e5da8c8de06848: docker inspect returned 1 Collecting main service artifacts

## Stump the models?

- oracle: 0/1 valid fail (0.0%)
- Timeouts excluded: 0; infra excluded: 0
- Band: `too_easy`
