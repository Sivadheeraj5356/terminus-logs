# This is an IAM policy-regression security audit task, not an application-buildin

Submission: `a8c5ea2f-5826-469d-92ea-cf36cbf37f42`  
Slug: `this-is-an-iam-policy-regression-security-audit-task-not-an`  
Latest archive: `a8c5ea2f-5826-469d-92ea-cf36cbf37f42_submission_2026-07-17T12_11_38.838Z.zip`  
Revisions: 1

## Task summary

This is an IAM policy-regression security audit task, not an application-building task: read `/app/task_file/policy_case.txt`, write `/app/task_file/output/policy_regression_report.json`, and include `/app/task_file/output/policy_regression_analyzer.rs` as a general Rust analyzer that compiles with `rustc --edition 2021 -C opt-level=3`, accepts `<input_path> <output_path>`, and computes the exact answer for any valid same-schema input within 120 seconds without test-harness, shell, Python, or hardcoded-case shortcuts. Verifier inputs have at most 10 principals, 16 actions, 14 resources, 7 request-context keys, 6 session-tag keys, 70 statements per bundle, and 8 invariants. The analyzer must compare every request in the finite universe formed by all principals, actions, resources, every `CONTEXT` value combination, and every `SESSION_TAG` assignment where each session tag is absent or has exactly one listed value. Rows are whitespace tokens: `PRINCIPAL id tags_csv|-`, `ACTION id`, `RESOURCE id value tags_csv|-`, `CONTEXT key values_csv`, `SESSION_TAG key values_csv`, `COND id op key values_csv`, `STMT bundle id layer effect principal_patterns_csv action_patterns_csv resource_patterns_csv condition_ids_csv|-`, and `INVARIANT id principal_patterns_csv action_patterns_csv resource_patterns_csv condition_ids_csv|-`. Bundles are `BASE` and `PATCHED`; layers are `IDENTITY`, `BOUNDARY`, `RESOURCE`, and `SCP`; effects are `ALLOW` and `DENY`. Tags are `key=value` pairs. Condition keys are `principal.<tag>`, `resource.<tag>`, `request.<context_key>`, or...

Required artifacts include: `/app/task_file/policy_case.txt`, `/app/task_file/output/policy_regression_report.json`, `/app/task_file/output/policy_regression_analyzer.rs`.

Author Anonymous tagged this **hard** security task (iam, policy-analysis, identity-security, access-control, regression-audit).

Time estimates: expert ~240.0 min, junior ~900.0 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `a8c5ea2f-5826-469d-92ea-cf36cbf37f42_submission_2026-07-17T12_11_38.838Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
