# Containment contract

`containment_plan.json` contains `incident_id`, `profile`, sorted `quarantine`, `retain`, `rotate`, and `require_manual_review` subject arrays, sorted `minimum_cut`, integer `blast_radius`, sorted `unresolved_conflicts`, `execution_order`, and `rollback_constraints`.

`execution_order` is `disable:<object>` rows in minimum-cut order followed by `quarantine:<subject>` rows in subject-ID order. `rollback_constraints` is the sorted evidence citation set from unresolved conflicts and active exceptions. `blast_radius` is the sum of disruption weights for services with no retained accepted path after the cut, including services that had no accepted path before the cut.

The bytes stored in `containment_plan.json` must be compact canonical JSON using UTF-8, sorted keys, separators `,` and `:`, `ensure_ascii=false`, and no trailing newline.
