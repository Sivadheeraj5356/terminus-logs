# We need a native security audit tool for a small infrastructure repo. Write a C 

Submission: `1654ef48-8ee1-4548-9145-f218d1d02eb9`  
Slug: `we-need-a-native-security-audit-tool-for-a-small-infrastruct`  
Latest archive: `1654ef48-8ee1-4548-9145-f218d1d02eb9_submission_2026-07-17T04_51_11.033Z.zip`  
Revisions in Dropbox: 2

## Task summary

We need a native security audit tool for a small infrastructure repo. Write a C program, build a compiled executable named `policy-auditor`, and use it to scan `/app/task_file/input_data/repo/` for risky production access policies; the default output must be `/app/task_file/output_data/findings.sarif`, and the executable must also support `policy-auditor <repo_dir> <sarif_output>`. Successful runs must return exit code 0 and write nothing to stderr. The output is exact-match SARIF 2.1.0 shape: top-level `version` is `2.1.0`, `$schema` is `https://json.schemastore.org/sarif-2.1.0.json`, `runs[0].tool.driver.name` is non-empty, `runs[0].tool.driver.rules` is non-empty, and each result has `ruleId`, `message.text`, `locations[0].physicalLocation.artifactLocation.uri` as a path relative to the scanned repo with no leading slash, and `locations[0].physicalLocation.region.startLine` as a 1-based integer. Report every applicable risky line; rules are additive and do not short-circuit when a file has multiple issues. Do not modify any input file.

Required artifacts include: `/app/task_file/input_data/repo/`, `/app/task_file/output_data/findings.sarif`, `/app/task_file/input_data/repo/infra/terraform/prod/`, `/app/task_file/input_data/repo/k8s/prod/`, `/app/task_file/input_data/repo/infra/iam/*.json`, `/app/task_file/input_data/repo/.github/workflows/`, `/app/task_file/input_data/repo/scripts/`.

Author Anonymous tagged this **hard** security task (policy-audit, sarif, infrastructure-security, static-analysis, c).

Time estimates: expert ~150 min, junior ~1200 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `1654ef48-8ee1-4548-9145-f218d1d02eb9_submission_2026-07-17T04_51_11.033Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
