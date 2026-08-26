# Our offline Conan builds need a small planner before the next CI image refresh. 

Submission: `0d572df7-f261-4ddb-984a-3e55c79d8ab7`  
Slug: `our-offline-conan-builds-need-a-small-planner-before-the-nex`  
Latest archive: `0d572df7-f261-4ddb-984a-3e55c79d8ab7_submission_2026-07-21T17_38_13.085Z.zip`  
Revisions: 2

## Task summary

Our offline Conan builds need a small planner before the next CI image refresh. The planner has to preserve earlier lock decisions, account for feature or option growth across ordered stages, and decide whether existing artifacts can be reused. Create an executable CLI at `/app/bin/conanplan`. The verifier runs it as `/app/bin/conanplan /app/input /app/output/plan.json` and also reruns the same executable against other compatible input directories. The command must accept exactly two positional arguments: an input directory and an output JSON path.

Required artifacts include: `/app/bin/conanplan`, `/app/input`, `/app/output/plan.json`, `/app/docs/conan-plan-spec.md`.

Author Anonymous tagged this **hard** build-and-dependency-management task (conan, package-id, profiles, binary-cache, lockfile).

Time estimates: expert ~180 min, junior ~540 min.

Harbor timeouts: agent 1200.0s, verifier 240.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `0d572df7-f261-4ddb-984a-3e55c79d8ab7_submission_2026-07-21T17_38_13.085Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
