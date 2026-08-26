# Endpoint Quarantine Approval Policy

The bundle JSON has `policy`, `assets`, and `actions`. Times are UTC strings such as `2026-05-17T13:00:00Z`; null `expires_at` means no end time. String enum values are lowercase and must be treated literally.

## Asset Outcomes

Each asset has `asset_id`, `zone`, `criticality`, `detected_at`, and `tags`.

An asset is blocked before plan selection if any tag starts with any string in `policy.deny_tag_prefixes`. Blocked assets get reason `blocked_tag` only. Other assets with no valid containment plan get `no_valid_plan`. Assets with a valid plan that are not the winner get `not_selected`. Reasons are emitted in this order: `blocked_tag`, `no_valid_plan`, `not_selected`.

Asset `status` is `accepted` for the winning asset and `rejected` for every other asset. Rejected entries still report their canonical plan if they had one; blocked or no-plan entries use empty selected arrays and zero numeric totals.

## Action Usability

An action is usable for an asset only if all local gates pass:

- `asset_id` matches the asset.
- `valid_from` is at or before `policy.evaluation_time`.
- If `expires_at` is not null, `policy.evaluation_time` is before it.
- `allowed_zones` is empty or contains the asset zone.
- No asset tag starts with any value in `blocked_tag_prefixes`.
- Every value in `families` appears in `policy.family_scores`.
- Every key in `family_confidence` appears in `policy.family_scores`.
- `owner` is listed in `policy.allowed_owners`.

Unusable actions do not create asset reasons.

## Valid Plans

For each unblocked asset, choose one canonical containment plan from usable actions. A plan may include at most one action per `action_type`.

Conflicts are symmetric for validation: a plan may not include two actions where either action id appears in the other's `conflicts_with`.

`requires_any` on an action is a list of action-id groups. For every group, at least one action id from that group must also be selected. Empty groups make the action impossible to include.

`requires_all_action_types` lists action types that must also be present in the selected plan. The selected action itself may satisfy a required action type.

Coverage is confidence based. Each selected action contributes confidence to the family keys in `family_confidence`. For any family listed in the action `families` array but missing from `family_confidence`, that action contributes confidence `100` for that family. A family is covered only when summed confidence for that family across the selected plan is at least `policy.family_min_confidence[family]`; if the policy has no entry for that family, the minimum is `1`. Confidence from unusable or unselected actions never counts.

A valid plan must:

- Cover every `policy.required_families` value.
- Have total covered-family `risk_score` at least `policy.threshold`.
- Use no more than `review_budget`, `outage_budget`, and `rule_slot_budget`.
- Have at least `min_distinct_owners` distinct owners.
- Respect `policy.owner_review_caps`; owners absent from the map have no owner-specific review cap.
- Respect `policy.max_actions_per_owner`; a value of `0` means unlimited.
- Respect `policy.zone_blast_radius_budget`; zones absent from the map have no blast-radius cap. Missing `blast_radius` on an action is `0`.

If total `outage_units` is greater than `escalation_outage_threshold`, the same selected plan must include an action whose `action_type` is exactly `management_approval`. This escalation rule is checked on the complete plan and still consumes budgets and an action type.

Empty plans are not valid unless the policy threshold and required family list are both empty.

## Scoring And Canonical Selection

Risk score is the sum of `policy.family_scores` for covered families, counted once per covered family. Output selected action ids sorted lexicographically. Output `selected_owners` as unique owner strings sorted lexicographically.

For each asset with valid plans, choose the canonical plan by comparing complete final plans.

If `tie_mode` is `risk_then_cost`, compare by higher `risk_score`, then lower `outage_units`, lower `review_minutes`, lower `rule_slots`, fewer selected actions, then lexicographically smaller sorted selected action id list.

If `tie_mode` is `cost_then_risk`, compare by lower `outage_units`, lower `review_minutes`, lower `rule_slots`, higher `risk_score`, fewer selected actions, then the same action-id list comparison.

The winner is the best asset with a valid plan. Compare assets by their canonical plan using the same `tie_mode`, then higher asset `criticality`, then later `detected_at`, then lexicographically smaller `asset_id`.

If there is no winner, top-level `status` is `rejected`, `winner` is null, selected arrays are empty, and numeric totals are `0`. Otherwise top-level `status` is `accepted`, and the top-level plan fields mirror the winning asset.
