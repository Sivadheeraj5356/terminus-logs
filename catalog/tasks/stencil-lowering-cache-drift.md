# # Stencil lowering cache drift

Submission: `18f85dc7-9228-4799-83a0-dd01b5ee2d16`  
Slug: `stencil-lowering-cache-drift`  
Latest archive: `18f85dc7-9228-4799-83a0-dd01b5ee2d16_submission_2026-07-04T10_50_20.857Z.zip`  
Revisions: 1

## Task summary

Our grid-operator compiler in `/app/environment` keeps a replay journal beside the build cache and a migration WAL under `/app/output/.cache/`. Incremental compiles have been drifting: spill totals change on repeated stage-two cache hits, migration leaves stale stage rows behind, WAL segments disagree with the journal epoch, replay generations diverge from the replay log, metrics rollups diverge from the live trace, and poisoned digest rows sometimes override a fresh recompute. Repair `/app/environment` so `node /app/environment/cli/driver.mjs compile --spec /app/environment/specs/operator.json --out /app/output` regenerates `/app/output/kernel.mjs`, `/app/output/pass.trace.json`, and `/app/output/metrics.json`. Static or manual writes to `/app/output` are not sufficient; hand-editing those outputs or bypassing the driver is not acceptable. `node /app/environment/cli/driver.mjs cache-reset` marks a migration before the next compile. `node /app/environment/cli/driver.mjs status --trace /app/output/pass.trace.json` prints register estimates from an existing trace.

Required artifacts include: `/app/environment`, `/app/output/.cache/`, `/app/environment/cli/driver.mjs`, `/app/environment/specs/operator.json`, `/app/output`, `/app/output/kernel.mjs`, `/app/output/pass.trace.json`, `/app/output/metrics.json`.

Author anonymous tagged this **hard** scientific-computing task (javascript, scientific-computing, codegen, optimization, simd).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 900s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `18f85dc7-9228-4799-83a0-dd01b5ee2d16_submission_2026-07-04T10_50_20.857Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
