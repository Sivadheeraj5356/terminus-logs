# Offline aisle traversal learner. Fix the sources under `/app/environment`, rebui

Submission: `c3ed481d-3eb2-4103-a69c-18b916844a10`  
Slug: `offline-aisle-traversal-learner-fix-the-sources-under-app-en`  
Latest archive: `c3ed481d-3eb2-4103-a69c-18b916844a10_submission_2026-07-14T13_43_17.861Z.zip`  
Revisions: 1

## Task summary

Offline aisle traversal learner. Fix the sources under `/app/environment`, rebuild `/app/bin/lane_matrix` from that workspace (see `/app/environment/docs/artifact_rules.md` for the release build invocation), then regenerate `/app/output/coverage_map.json` with the command below. `/app/bin/lane_matrix --fixtures /app/fixtures --spec /app/spec --out /app/output/coverage_map.json`

Required artifacts include: `/app/environment`, `/app/bin/lane_matrix`, `/app/environment/docs/artifact_rules.md`, `/app/output/coverage_map.json`, `/app/fixtures`, `/app/spec`.

Author anonymous tagged this **hard** machine-learning task (coverage-map, pick-path, warehouse, formal, adversarial).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `c3ed481d-3eb2-4103-a69c-18b916844a10_submission_2026-07-14T13_43_17.861Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
