# Emergency Break-Glass Access Adjudication Contract

This contract defines the offline security report for signed emergency privileged-access events. The report decides which break-glass activation attempts are allowed, stepped up, or denied under access-control policy. All IDs are case-sensitive ASCII strings. Input object key order is not meaningful. Input array order is not meaningful except where this contract says it is preserved in the output.

## Input JSON

The input has exactly these top-level fields:

- `policy`: object with `approval_window`, `control_window`, `max_route_hops`, `step_up_after`, `deny_above`, `clearance_order`, and `risk_signal_scores`.
- `principals`: array of principal objects.
- `resources`: array of protected resource objects.
- `gateways`: array of directed gateway objects.
- `events`: array of authorization event objects.

`policy.approval_window`, `policy.control_window`, `policy.max_route_hops`, `policy.step_up_after`, and `policy.deny_above` are integers. `policy.clearance_order` is strongest to weakest; a lower index is stronger. `policy.risk_signal_scores` maps risk signal strings to integer scores.

Each principal has string `id`, `org`, `site`, `clearance`, and `secret`; boolean `available`; integer `active_from`, `active_until`, and `revoked_after`; and boolean `external`. A `revoked_after` value of `0` means not revoked.

Each resource has string `id`, `zone`, and `min_clearance`; string arrays `required_roles` and `required_controls`; integer `min_distinct_orgs`, `min_distinct_sites`, and `base_risk`; and arrays `separation_pairs` and `org_separation_pairs`, each containing two-element string arrays.

Each gateway has string `id`, `from_zone`, and `to_zone`; and boolean `initially_locked`. Gateways are directed. A gateway from `A` to `B` does not imply a gateway from `B` to `A`.

Each event has string `id`, `type`, `session`, `principal`, `resource`, `role`, `control`, `gateway`, `from_zone`, `to_zone`, `token`, `challenge`, and `signature`; string array `risk_signals`; and integer `revision`, `time`, `ingest_seq`, and `expires_at`.

Valid event `type` values are `open`, `approve`, `control`, `hop`, `activate`, `close`, `lock`, and `unlock`. Event IDs can repeat; principal, resource, and gateway IDs are otherwise unique within their arrays. Every event names a known principal. Events that use a resource or gateway name a known resource or gateway. Empty strings and empty arrays are valid for fields not used by a particular event type.

## Event Retention and Replay Order

Duplicate event IDs are compacted to one retained row. The retained row is selected by highest `revision`, then later `time`, then higher `ingest_seq`, then lexicographically smaller `session`. Discarded duplicate rows have no state effect and do not appear in the report.

Retained events are replayed in ascending `time`, then ascending `ingest_seq`, then lexicographic `id`.

Gateway lock state, privileged sessions, approvals, controls, route position, consumed activation tokens, and final sessions are stateful across that replay order.

## Signature Contract

The event `signature` is lowercase hex HMAC-SHA256 keyed by the principal `secret`. The signed transcript is these sixteen values joined by newline:

1. `id`
2. decimal `revision`
3. `type`
4. `session`
5. `principal`
6. `resource`
7. `role`
8. `control`
9. `gateway`
10. `from_zone`
11. `to_zone`
12. `token`
13. `challenge`
14. decimal `time`
15. decimal `expires_at`
16. canonical risk signals

Canonical risk signals are the event `risk_signals` array deduplicated, sorted lexicographically, and joined with commas.

## Event Findings

Every retained event appears in `event_findings` in replay order. An event finding has `status: "accepted"` when its reason list is empty, otherwise `status: "ignored"`.

Reasons appear only in this order:

`principal_unavailable`, `principal_inactive`, `principal_revoked`, `bad_signature`, `session_missing`, `session_closed`, `session_expired`, `challenge_mismatch`, `duplicate_open`, `role_not_required`, `clearance_too_low`, `control_not_required`, `gateway_mismatch`, `gateway_locked`, `route_too_long`

Basic principal and signature reasons apply to every event:

- `principal_unavailable`: the event principal has `available: false`.
- `principal_inactive`: event `time` is before principal `active_from` or after principal `active_until`.
- `principal_revoked`: principal `revoked_after` is nonzero and event `time >= revoked_after`.
- `bad_signature`: the HMAC transcript verification fails.

Session reasons apply to `approve`, `control`, `hop`, `activate`, and `close` events:

- `session_missing`: no accepted `open` event has created the event session.
- `session_closed`: the session was closed by an earlier accepted `close` event.
- `session_expired`: event `time` is greater than the session `expires_at`.
- `challenge_mismatch`: event `challenge` differs from the session challenge.

Type-specific reasons are additive and still accumulate with applicable basic and session reasons:

- `duplicate_open`: an `open` event names a session that already exists and is not closed.
- `role_not_required`: an `approve` event role is not listed in the session resource `required_roles`.
- `clearance_too_low`: an `approve` event principal's clearance is weaker than the session resource `min_clearance`, or either clearance string is absent from `policy.clearance_order`.
- `control_not_required`: a `control` event control is not listed in the session resource `required_controls`.
- `gateway_mismatch`: a `hop`, `lock`, or `unlock` event's gateway does not match the event `from_zone` and `to_zone`; for `hop`, this reason also applies when `from_zone` differs from the session current zone.
- `gateway_locked`: a `hop` event uses a gateway that is locked at that event time.
- `route_too_long`: accepting a `hop` event would make the session hop count greater than `policy.max_route_hops`.

An ignored event has no state effect. An accepted `activate` event always produces a decision, even when that decision is denied by quorum, route, replay, control, or risk rules.

## State Effects

An accepted `open` creates a session with the event `session`, `resource`, `challenge`, `expires_at`, requester principal, current zone equal to the requester's principal `site`, hop count `0`, activation count `0`, state `open`, empty approvals, empty controls, and route containing only the starting zone.

An accepted `approve` records an approval for the session with the event ID, role, principal, and time.

An accepted `control` records a control observation for the session with the event ID, control, principal, and time.

An accepted `hop` appends `to_zone` to the session route, sets current zone to `to_zone`, and increments hop count.

An accepted `lock` sets the named gateway locked. An accepted `unlock` sets it unlocked.

An accepted `activate` does not change route position. If its decision status is `allow` or `step_up`, it consumes the session token, increments activation count, and sets session state to `activated`. A denied activation does not consume the token and does not change the session state.

An accepted `close` sets session state to `closed`.

## Activation Decisions

Every retained `activate` event appears in `decisions` in replay order. Decision reasons appear only in this order:

`event_ignored`, `token_replayed`, `route_incomplete`, `missing_quorum`, `org_diversity`, `site_diversity`, `separation_violation`, `missing_control`, `risk_too_high`

If the activation event finding is ignored, the decision has reason `event_ignored`. The other decision rules are still evaluated when the session exists and is not closed, so reasons can accumulate with `event_ignored` when state is available.

Usable approvals for an activation are accepted approval events for the same session where all of these are true at activation time:

- `activation.time - approval.time <= policy.approval_window`
- the approval principal is available
- the approval principal is active at activation time
- the approval principal is not revoked at activation time

Usable controls are accepted control events for the same session where `activation.time - control.time <= policy.control_window`.

For each required role on the session resource, at least one usable approval for that role must exist. If any required role is missing, emit one `missing_quorum` reason, not one per role.

Distinct orgs and sites are counted from usable approval principals. If the org count is less than the resource `min_distinct_orgs`, emit `org_diversity`. If the site count is less than `min_distinct_sites`, emit `site_diversity`.

For each resource `separation_pairs` entry `[left, right]`, no single principal may have usable approvals for both roles. For each `org_separation_pairs` entry `[left, right]`, no single org may have usable approvals for both roles. Emit one `separation_violation` if any principal or org separation rule is violated.

For each required control, at least one usable control for that control must exist. If any required control is missing, emit one `missing_control`, not one per control.

Emit `route_incomplete` when the session current zone is not the resource zone.

Emit `token_replayed` when the session token was already consumed by an earlier `allow` or `step_up` decision.

Risk score is computed for every activation decision as:

- session resource `base_risk`
- plus each unique activation event risk signal score from `policy.risk_signal_scores`; unknown signals add `0`
- plus `6` for each distinct usable approval principal with `external: true`
- plus `4` when `2 * (activation.time - session.open_time) > (session.expires_at - session.open_time)`
- plus `3` when session hop count equals `policy.max_route_hops`

Emit `risk_too_high` when risk score is greater than `policy.deny_above`.

Decision status is `deny` if any decision reason is present. Otherwise it is `step_up` if risk score is greater than `policy.step_up_after`, else `allow`.

## Output JSON

Write a JSON object with exactly these top-level fields:

- `event_findings`: array in retained event replay order.
- `decisions`: array in retained activation event replay order.
- `final_sessions`: array sorted by session ID.
- `consumed_sessions`: sorted array of session IDs whose token was consumed by an `allow` or `step_up` decision.

Each `event_findings` object has string `id`, string `type`, string `status`, and ordered string array `reasons`.

Each `decisions` object has string `id`, `session`, `resource`, and `status`; integer `risk_score`; ordered string array `reasons`; `approvals`, `controls`, and `route` arrays.

The `approvals` array has one row for each resource required role, in the resource `required_roles` order. Each row has string `role` and string array `providers`, sorted lexicographically as `event_id:principal_id` for usable approvals of that role.

The `controls` array has one row for each resource required control, in the resource `required_controls` order. Each row has string `control` and string array `providers`, sorted lexicographically as `event_id:principal_id` for usable controls of that control.

The `route` array is the session route after replaying events before the activation decision. If the session is missing, `approvals`, `controls`, and `route` are empty arrays, the decision `resource` is the activation event resource string, and risk score is `0`.

Each `final_sessions` object has string `session`, `resource`, `state`, and `current_zone`; integer `hop_count` and `activation_count`. Sessions are included only if created by an accepted `open`.

The verifier parses JSON, so object key order does not matter. Array order, field names, strings, booleans, integers, and empty arrays must match this contract exactly.
