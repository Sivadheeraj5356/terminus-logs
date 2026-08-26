# Continuing in the same `/app` repository, this milestone concerns the seven `bvm

Submission: `8e9527c9-ed98-47fd-9963-125c5aa96c19`  
Slug: `continuing-in-the-same-app-repository-this-milestone-concern`  
Latest archive: `8e9527c9-ed98-47fd-9963-125c5aa96c19_submission_2026-07-06T04_13_08.278Z.zip`  
Revisions in Dropbox: 3

## Task summary

Continuing in the same `/app` repository, this milestone concerns the seven `bvm` subcommands that derive deeper analyses from a bytecode module. `/app/docs/bvm-spec.md` remains the authoritative data contract for the type lattice, the join (least-upper-bound) of stack and local types at control-flow merge points, definite assignment of locals, and the exact output of every command; `/app/data` holds a corpus of input modules to run the tool against. The subcommands in scope are: `verify` (abstract-interpretation dataflow to a fixpoint over each function's control-flow graph, printing a verified or rejected verdict per function), `dom` (the immediate dominator of every reachable block), `analyze` (reachable blocks, dead blocks and the maximum operand-stack depth), `report` (a per-function summary followed by an FNV-1a digest), `run` and `trace` (execution of `main` to a result or a trap), and `batch` (processing a manifest of modules into per-model lines and a digest).

Required artifacts include: `/app/docs/bvm-spec.md`, `/app/data`, `/app/bin/bvm`.

Author anonymous tagged this **hard** data-processing task (go, bytecode, static-analysis, abstract-interpretation, type-checking, dataflow, data-transformation).

Time estimates: expert ~240 min, junior ~540 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8e9527c9-ed98-47fd-9963-125c5aa96c19_submission_2026-07-06T04_13_08.278Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
