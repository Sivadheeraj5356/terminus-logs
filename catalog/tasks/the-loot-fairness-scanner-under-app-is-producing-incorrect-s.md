# The loot fairness scanner under `/app` is producing incorrect session reports af

Submission: `97fce60e-fc47-4d51-94ce-2c790b36a89a`  
Slug: `the-loot-fairness-scanner-under-app-is-producing-incorrect-s`  
Latest archive: `97fce60e-fc47-4d51-94ce-2c790b36a89a_submission_2026-07-09T13_36_55.662Z.zip`  
Revisions: 1

## Task summary

The loot fairness scanner under `/app` is producing incorrect session reports after a replay refactor. Fix the implementation by editing Go code only under `/app/faircore` and `/app/rollbench`; do not modify `/app/dropvault`, `/app/go.mod`, or `/app/Makefile`. Behavior and output requirements are defined by `/app/dropvault/fairness_rules.json` and the rule files it references. Implement all of those rules exactly.

Required artifacts include: `/app/faircore`, `/app/rollbench`, `/app/dropvault`, `/app/go.mod`, `/app/Makefile`, `/app/dropvault/fairness_rules.json`, `/app/out/lootfair`, `/app/out/fairness_report.json`.

Author anonymous tagged this **hard** build-and-dependency-management task (go, fairness, rng, analytics).

Time estimates: expert ~240.0 min, junior ~480.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `97fce60e-fc47-4d51-94ce-2c790b36a89a_submission_2026-07-09T13_36_55.662Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
