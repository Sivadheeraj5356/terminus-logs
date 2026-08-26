# This is an IAM policy-regression security audit task, not an application-buildin

- **UUID:** `a8c5ea2f-5826-469d-92ea-cf36cbf37f42`
- **Slug:** `this-is-an-iam-policy-regression-security-audit-task-not-an`
- **Category:** security
- **Difficulty:** hard

## Summary

This is an IAM policy-regression security audit task, not an application-building task: read `/app/task_file/policy_case.txt`, write `/app/task_file/output/policy_regression_report.json`, and include `/app/task_file/output/policy_regression_analyzer.rs` as a general Rust analyzer that compiles with `rustc --edition 2021 -C opt-level=3`, accepts `<input_path> <output_path>`, and computes the exact answer for any valid same-schema input within 120 seconds without test-harness, shell, Python, or hardcoded-case shortcuts. Verifier inputs have at most 10 principals, 16 actions, 14 resources, 7 request-context keys, 6 session-tag keys, 70 statements per bundle, and 8 invariants.

The analyzer must compare every request in the finite universe formed by all principals, actions, resources, every `CONTEXT` value combination, and every `SESSION_TAG` assignment where each session tag is absent or has exactly one listed value. Rows are whitespace tokens: `PRINCIPAL id tags_csv|-`, `ACTION id`, `RESOURCE id value tags_csv|-`, `CONTEXT key values_csv`, `SESSION_TAG key values_csv`, `COND id op key values_csv`, `STMT bundle id layer effect principal_patterns_csv action_patterns_csv resource_patterns_csv condition_ids_csv|-`, and `INVARIANT id principal_patterns_csv action_patterns_csv resource_patterns_csv condition_ids_csv|-`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
