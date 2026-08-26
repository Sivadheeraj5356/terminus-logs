# Model Release Contract

`model-release` reads a JSON document with `subjects`, versioned `releases`, and `queries`, then prints one JSON object with an `assignments` array preserving query order.

Each assignment includes the query `id`, canonical `subject`, `model`, `status`, `variant`, `source`, and `blockedBy`. Use `status: "active"` when a model variant is selected, `status: "missing"` when no release snapshot is effective at the query time, and `status: "blocked"` when a prerequisite model or cycle prevents assignment. `source` and `blockedBy` are `null` when they do not apply.

Subjects may be addressed by `id` or any `aliases`, but output the canonical `id`. For a query, use the latest snapshot for the requested model whose numeric `effective` is not later than `at`; if multiple snapshots share the same `effective`, the later input snapshot is newer. Ignore snapshots whose `expires` is present with `at >= expires`.

Before selecting a variant, evaluate every prerequisite in the selected snapshot for the same canonical subject and time. A prerequisite mismatch blocks with `blockedBy: "prerequisite:<model>"`. Recursive prerequisite cycles block with `blockedBy: "cycle"`.

Variant selection follows this precedence:

1. Matching overrides.
2. Matching cohorts.
3. Rollout variants.
4. Snapshot default.

Within a snapshot, later matching `overrides` replace earlier overrides. An override with `until` is active only while `at < until`. Matching cohorts are ordered by highest numeric `priority`, then later cohort order; each cohort `when` maps subject attribute names to an exact value or an array of allowed values.

Rollout variants use a deterministic SHA-256 bucket of `<salt>|<model>|<canonical-subject>`. Use the first eight hex characters as an unsigned 32-bit integer divided by `0x100000000`. Variant weights are cumulative bucket ranges in the order listed. If no range matches, use `default`.

Source strings are `<release-id>:override:<subject>`, `<release-id>:cohort:<id>`, `<release-id>:rollout`, `<release-id>:default`, or `null` for missing and blocked assignments.
