# Trust assessment contract

`trust_assessment.json` is an object with `incident_id`, `profile`, `policy_revision`, `evidence_set_digest`, `conflict_classifications`, and `assessments`.

First apply the case overlay to a copy of the base evidence as described in `evidence_contract.md`; call the result `merged_evidence` and retain the original case JSON object as `profile`. The evidence-set digest is lowercase SHA-256 of canonical JSON (UTF-8, sorted keys, separators `,` and `:`, no ASCII escaping) of the exact two-key wrapper `{"evidence": merged_evidence, "profile": profile}`. It is not a flat merge and is not a digest of either object alone.

The bytes stored in `trust_assessment.json` must themselves be that compact canonical JSON encoding, with no indentation, spaces after separators, or trailing newline. This file-level rule is separate from digest calculation.

Conflict rows contain `conflict_id`, `classification`, `controlling_source` (string or null), and sorted `evidence`. Classification is one of `PRECEDENCE_RESOLVED`, `SCOPE_DISTINGUISHED`, `SUPERSEDED`, or `UNRESOLVED`.

Assessments partition every service subject and sort by `subject_id`. Each contains `subject_id`, `disposition` (`RETAIN`, `QUARANTINE`, `ROTATE`, `MANUAL_REVIEW`), `reason_code` (`VALID_PATH`, `COMPROMISED_PATH`, `QUORUM_FAILURE`, `REVOKED`, `EXCEPTION_SCOPE`, `UNRESOLVED_POLICY`), sorted `accepted_paths`, sorted `rejected_paths`, sorted `compromise_sources`, sorted `evidence`, `quorum` with integer `required`, integer `counted`, and sorted `witness_ids`, plus one `counterfactual` object.

Compute witness eligibility and independence once for the merged case. Every assessment row repeats that same case-level quorum object; do not compute a service- or path-local witness count.

Disposition is `RETAIN` when at least one path is accepted, `MANUAL_REVIEW` when no path is accepted and any rejected path has `UNRESOLVED_POLICY`, and otherwise `QUARANTINE`. `ROTATE` is reserved by this schema and is not selected by TS-7 for this incident corpus. The reason code is `VALID_PATH` whenever at least one path is accepted; otherwise it is the lexicographically smallest rejection reason among that subject's paths.

The counterfactual has string keys `changed_fact` and `resulting_disposition`. It names the lexicographically first counted witness as `remove witness <id>` and reports the disposition after removing it. If no witness is counted, use `remove exception <id>` for the applicable exception; otherwise use `remove path <id>`. Recompute the complete subject disposition after removing that fact; do not merely describe intent.
