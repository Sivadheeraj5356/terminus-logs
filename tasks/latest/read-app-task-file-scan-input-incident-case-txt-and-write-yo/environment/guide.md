# Calibration Scheduling Specification

This document contains the full task semantics for `incident_case.txt`.

## Input Layout

Rows are `PARAM`, `SCENARIO`, `APPROVAL`, `HOST`, `IDENTITY`, `FOOTHOLD`, `EDGE`, `CROWN`, `WORKFLOW`, and `EVIDENCE`.

- `SCENARIO` is `scenario_id confidence_weight`.
- `HOST` is `host_id zone owner criticality`.
- `IDENTITY` is `identity_id owner privilege_tier`.
- `FOOTHOLD` is `scenario_id foothold_id identity_id host_id`.
- `EDGE` is `edge_id src_identity_id src_host_id dst_identity_id dst_host_id technique`.
- `CROWN` is `crown_id identity_id host_id impact_points`.
- `WORKFLOW` is `workflow_id start_identity_id start_host_id end_identity_id end_host_id continuity_penalty_points`.
- `EVIDENCE` is `evidence_id identity_id host_id value_points`.

Treat each explicit `identity_id@host_id` pair that appears anywhere in those rows as a node. Do not invent the full identity-by-host cross-product.

## Actions

There are no action rows. Derive actions yourself.

For every identity derive `ACT_RESET_<identity_id>` and `ACT_DISABLE_<identity_id>`.

- `reset_identity`
  - owner: `identity.owner`
  - approval: `APR_<owner>`
  - disruption: `2` for `USER`, `3` for `SERVICE`, `4` for `ADMIN`
  - blocks outbound edges from that identity when the technique is `TOKEN_REUSE`, `APPLOGIN`, `OAUTH`, or `APIKEY`
  - does not clear an existing compromise
- `disable_identity`
  - same approval bucket
  - disruption: `5` / `6` / `8`
  - blocks every edge whose source or destination identity is that identity
  - clears every node whose identity matches

For every host derive `ACT_CONTAIN_<host_id>` and `ACT_ISOLATE_<host_id>`.

- `contain_host`
  - owner: `host.owner`
  - approval: `APR_<owner>`
  - disruption: `3` for `STANDARD` and `4` for `CRITICAL`
  - blocks outbound edges from that host when the technique is `WINRM` or `RDP`
  - does not clear an existing compromise
- `isolate_host`
  - same approval bucket
  - disruption: `6` for `STANDARD` and `8` for `CRITICAL`
  - blocks every edge whose source or destination host is that host
  - clears every node on that host

For every host that has at least one `EVIDENCE` row derive `ACT_SNAPSHOT_<host_id>`.

- `snapshot_host`
  - owner: `IR`
  - approval: `APR_IR`
  - disruption: `1` for `STANDARD` and `2` for `CRITICAL`
  - does not block edges
  - does not clear compromise
  - captures every evidence row on that host

## Schedule Rules

You have `wave_count` waves. In each wave choose nothing, one action, or two actions. An action may appear at most once in the whole schedule. Review cost is the union of approval ids touched anywhere in the schedule, counted once each. The schedule is valid only if total review minutes are at most `max_total_review_minutes`, at least `min_distinct_owners` distinct owners appear in the schedule, and final preserved evidence value is at least `min_preserved_evidence_points`.

Simulation is per scenario. Start each scenario from its own `FOOTHOLD` rows. A wave applies all chosen actions simultaneously, then the attacker spreads exactly one hop from every currently compromised node across any edge that is still unblocked. Blocked edges persist into later waves. If a crown node is ever compromised in a scenario, that crown is lost for that scenario permanently even if a later disable or isolate clears the node. A workflow is broken for a wave if the cumulative blocked-edge set leaves no directed path from its start node to its end node.

Evidence is global, not per scenario. A snapshot captures the matching evidence rows immediately and permanently. Unsnapshotted evidence is destroyed permanently if a wave uses `disable_identity` on that evidence row's identity or `isolate_host` on that evidence row's host. Because actions in the same wave apply together, a same-wave snapshot and destructive clear still preserves that evidence.

## Scoring and Canonicalization

Score exactly as `response_score_units = (sum over scenarios of scenario.confidence_weight * protected_crown_impact_points * 100) + (preserved_evidence_points * 25) - (sum over waves of broken_workflow_continuity_penalty_points * 10) - total_disruption_points`. A crown counts as protected in a scenario only if it was never lost there. If two schedules tie on `response_score_units`, prefer the one with lower `total_review_minutes`. If that still ties, compare the waves left to right using each wave's sorted `action_ids` and keep the lexicographically smaller schedule.

Write one JSON object with `response_score_units`, `total_disruption_points`, `total_review_minutes`, `preserved_evidence_points`, `preserved_evidence_ids`, `scenario_results`, and `waves`. `response_score_units`, `total_disruption_points`, `total_review_minutes`, `preserved_evidence_points`, and `wave_index` must be JSON integers, not floats. `preserved_evidence_ids` must stay in original `EVIDENCE` row order. `scenario_results` must stay in `SCENARIO` row order, and each entry needs `scenario_id` plus `protected_crown_ids` in `CROWN` row order. `waves` must have exactly `wave_count` entries, in order. Each wave needs `wave_index`, `action_ids`, `broken_workflow_ids`, and `actions`. `wave_index` is 1-based. Keep `action_ids` sorted ascending inside each wave, keep `actions` in that same order, and keep `broken_workflow_ids` in `WORKFLOW` row order.

Each action object needs `action_id`, `action_type`, `target_id`, `owner`, `disruption_points`, `approval_ids`, `captured_evidence_ids`, `cleared_node_ids`, and `blocked_edge_ids`. Use these exact lowercase `action_type` strings: `snapshot_host`, `reset_identity`, `disable_identity`, `contain_host`, and `isolate_host`. `captured_evidence_ids` is the full list of evidence rows that action captures by rule, so it is non-empty only for snapshot actions and it stays in original `EVIDENCE` row order. `cleared_node_ids` should use `identity_id@host_id`, be sorted lexicographically, and list every node the action would clear by rule, not just the nodes that happened to be compromised when it ran. For this field, the node universe is the explicit node set described above, not the full identity-by-host cross-product. `blocked_edge_ids` must stay in original `EDGE` row order.
