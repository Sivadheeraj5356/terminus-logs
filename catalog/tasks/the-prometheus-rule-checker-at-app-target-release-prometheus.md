# The Prometheus rule checker at `/app/target/release/prometheus-rule-checker` val

Submission: `a72bd6ac-4fa9-400e-a736-c40cd478f7a9`  
Slug: `the-prometheus-rule-checker-at-app-target-release-prometheus`  
Latest archive: `a72bd6ac-4fa9-400e-a736-c40cd478f7a9_submission_2026-07-08T11_36_14.848Z.zip`  
Revisions: 3

## Task summary

The Prometheus rule checker at `/app/target/release/prometheus-rule-checker` validates Prometheus recording and alerting rules. It reads rule definitions from `/app/data/rules.json` and produces a validation report at `/app/output/report.json`. The tool has bugs that cause incorrect validation results. Fix all bugs so that the tool produces a correct report according to standard Prometheus rule validation conventions.

Required artifacts include: `/app/target/release/prometheus-rule-checker`, `/app/data/rules.json`, `/app/output/report.json`.

Author anonymous tagged this **hard** system-administration task (prometheus, monitoring, rule-validation, config-parsing).

Time estimates: expert ~60.0 min, junior ~120.0 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `a72bd6ac-4fa9-400e-a736-c40cd478f7a9_submission_2026-07-08T11_36_14.848Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
