The emergency-access security ledger review uses eight tab-separated evidence files and one JSON ledger package. Default paths are:

- `/app/input_data/principals.tsv`
- `/app/input_data/resources.tsv`
- `/app/input_data/tickets.tsv`
- `/app/input_data/approvers.tsv`
- `/app/input_data/requests.tsv`
- `/app/input_data/approvals.tsv`
- `/app/input_data/events.tsv`
- `/app/input_data/revocations.tsv`

Each path can be overridden by the matching environment variable named in `instruction.md`. The output path defaults to `/app/output_data/breakglass_ledger.json` and is overridden by `BREAKGLASS_OUT`.

Schemas:

- `principals.tsv`: `principal`, `role`, `team`, `status`, `mfa`, `manager`, `zones`, `max_active`
- `resources.tsv`: `resource`, `zone`, `tier`, `owner_team`, `max_minutes`, `dual_control`, `forbidden_roles`, `allowed_cidrs`, `privileged_commands`
- `tickets.tsv`: `ticket`, `requester`, `resource`, `opened_ts`, `closed_ts`, `emergency`, `allowed_cidrs`, `allowed_commands`
- `approvers.tsv`: `approver`, `team`, `status`, `zones`, `authority`, `secret`
- `requests.tsv`: `request_id`, `requester`, `resource`, `start_ts`, `end_ts`, `ticket`, `reason`, `source_ip`
- `approvals.tsv`: `approval_id`, `request_id`, `approver`, `decision`, `ts`, `signature`
- `events.tsv`: `event_id`, `request_id`, `ts`, `actor`, `session_id`, `source_ip`, `command`, `prev_hash`, `event_hash`
- `revocations.tsv`: `principal`, `resource`, `effective_ts`, `reason`

Comma-list fields use `-` for empty. A zone list containing `*` allows every zone. A forbidden role, allowed command, or privileged command matches exactly after trimming whitespace. `allowed_cidrs` contains IPv4 CIDR ranges such as `10.0.0.0/24`; `-` means no network restriction. IPv4 CIDR matching uses unsigned 32-bit network masks, and `/0` matches every IPv4 address. In `tickets.tsv`, `closed_ts=-` means the ticket is still open.

Signature and event integrity rules:

- An approval signature is valid only when it equals lowercase SHA-256 hex of `secret|approval_id|request_id|approver|decision|ts`, where `secret` comes from the approver row.
- A missing approver makes the signature invalid.
- An event hash is valid only when it equals lowercase SHA-256 hex of `prev_hash|event_id|request_id|ts|actor|session_id|source_ip|command`.
- The first event row must have `prev_hash` equal to `GENESIS`.
- Every later event row must have `prev_hash` equal to the previous physical row's `event_hash` value. This chain rule uses the file order, even when the previous event hash is itself invalid.

Request eligibility:

- The requester must exist in `principals.tsv`.
- The requester must have `status` equal to `active`.
- The requester must have `mfa` equal to `true`.
- The requester must be allowed for the resource zone through `zones`.
- The requester's role must not appear in the resource's `forbidden_roles`.
- The request duration in whole minutes must be no greater than the resource's `max_minutes`.
- A request for a resource with `tier` equal to `critical` must have a ticket of exactly `INC-` plus six digits or `CHG-` plus six digits.

Ticket binding:

- For every request whose `ticket` is not `-`, the ticket must exist in `tickets.tsv`.
- If the ticket exists, its `requester` and `resource` must equal the request requester and resource.
- If the ticket exists, `opened_ts` must be less than or equal to the request `start_ts`, and `closed_ts` must be `-` or greater than or equal to the request `end_ts`.
- Critical-resource requests must use a ticket whose `emergency` value is `true`.
- Ticket binding failures do not by themselves make the request unauthorized; they are tracked separately from requester eligibility and approval control.

Approval validity:

- Only `decision=approve` rows count.
- The approval signature must be valid.
- The approver must exist, have `status=active`, and be allowed for the resource zone.
- `authority=security` is valid for any resource when the zone rule passes.
- `authority=owner` is valid only when the approver's team equals the resource's `owner_team`.
- The approver must not equal the requester.
- The approver must not share the requester's manager.
- The approval timestamp must be less than or equal to the request `start_ts`.
- If `dual_control=true`, at least two valid approvals from distinct approvers and distinct approver teams are required. Otherwise, one valid approval is required.

A request is authorized only when requester eligibility passes, duration and critical-ticket checks pass, and the approval-count rule passes.

Ledger controls:

- Unless a control description says otherwise, request-level ledger entries use the request `requester` as `principal` and the request `resource` as `resource`; event-level ledger entries use the event `actor` as `principal` and the event's request resource as `resource`.
- `requester-not-eligible`, severity `critical`: one per request with requester eligibility failures. Reasons are selected from `missing_requester`, `inactive_requester`, `mfa_missing`, `zone_not_allowed`, and `forbidden_role`.
- `approval-control-failure`, severity `critical`: one per request with approval validity or approval-count failures. Reasons are selected from `signature_invalid`, `approver_inactive`, `approver_zone_not_allowed`, `approver_authority_invalid`, `self_approval`, `shared_manager`, `late_approval`, and `insufficient_approvals`. Evidence includes the request and every approval row that contributes one of those reasons.
- `duration-or-ticket-violation`: one per request with duration or ticket failures. Severity is `high` when `duration_exceeds_max` is present, otherwise `medium`. Reasons are selected from `duration_exceeds_max` and `critical_ticket_invalid`.
- `ticket-binding-violation`, severity `high`: one per request with ticket binding failures. Reasons are selected from `ticket_missing`, `ticket_requester_mismatch`, `ticket_resource_mismatch`, `ticket_not_open_for_window`, and `ticket_not_emergency_for_critical`. Evidence includes the request and the ticket when it exists, using `ticket:<ticket>`.
- `ledger-integrity-break`, severity `critical`: one per event with invalid event hash or broken chain link. Reasons are selected from `event_hash_invalid`, `first_prev_not_genesis`, and `prev_hash_mismatch`. If the event's request is missing, use `unknown` as `resource`.
- `access-outside-window`, severity `high`: one per event whose timestamp is before the request start or after the request end. Reason is `event_outside_request_window`.
- `post-revocation-access`, severity `critical`: one per event whose actor/resource pair has a revocation with `effective_ts` less than or equal to the event timestamp. Use the earliest matching revocation as evidence. Reason is `revocation_effective`.
- `unapproved-command`, severity `high`: one per event where the command is in the resource's `privileged_commands` and either the request is not authorized or the event actor is not the request requester. Reasons are selected from `request_not_authorized` and `actor_mismatch`.
- `source-ip-drift`, severity `medium`: one per event whose source IP differs from the request source IP. Reason is `source_ip_changed`.
- `concurrent-session-limit`, severity `medium`: one per requester when more authorized request windows overlap for that requester than the principal's `max_active`. Evidence contains all request IDs in every exceeding overlap group, deduplicated and sorted. Reason is `max_active_exceeded`; the output `resource` is `multiple`.
- `network-boundary-violation`, severity `high`: one per request whose `source_ip` is outside the resource `allowed_cidrs`, and one per event whose `source_ip` is outside the resource `allowed_cidrs`. Reasons are `request_source_out_of_range` and `event_source_out_of_range`.
- `approval-concentration-risk`, severity `medium`: one per approver who has valid approvals for more than two distinct critical-resource requests whose request `start_ts` values fall in any inclusive 180-minute window. Only approval rows that are valid under the approval validity rules count, regardless of whether the request as a whole is authorized. Evidence contains every approval ID from every exceeding window for that approver, deduplicated and sorted. The output `principal` is the approver, the output `resource` is `multiple`, and the reason is `critical_approval_burst`.
- `ticket-scope-violation`, severity `high`: one per request whose request `source_ip` is outside the ticket `allowed_cidrs`, and one per event whose source IP is outside the ticket `allowed_cidrs` or whose command is outside the ticket `allowed_commands`. Only evaluate this control when the request ticket exists. Evidence includes the ticket and either the request or event that violated the scope. Reasons are selected from `request_source_outside_ticket_cidr`, `event_source_outside_ticket_cidr`, and `event_command_outside_ticket_scope`.
- `session-handoff-detected`, severity `high`: one per non-empty `session_id` when events with that same session ID have more than one actor or more than one source IP. Evidence contains all event IDs for that session. The output `principal` is `multiple`, the output `resource` is `multiple`, and reasons are selected from `session_actor_changed` and `session_source_ip_changed`.

Evidence strings:

- request rows: `request:<request_id>`
- approval rows: `approval:<approval_id>`
- event rows: `event:<event_id>`
- ticket rows: `ticket:<ticket>`
- revocation rows: `revocation:<principal>:<resource>:<effective_ts>`

For each ledger entry, evidence is sorted lexicographically and deduplicated. `first_evidence` is the first string in that sorted list. Reason codes are sorted lexicographically and deduplicated.

If a row references a missing request or resource, emit the relevant rule that can be evaluated and use `unknown` for the missing principal or resource output field. Missing-request events can still produce `ledger-integrity-break`; other event controls require the request and resource.

Final ledger package:

- Sort `ledger_entries` by `first_evidence`, then `control`, then `principal`, then `resource`.
- Assign `entry_id` after sorting as `BRK-0001`, `BRK-0002`, and so on.
- `severity_index` counts ledger entries by severity.
- The output JSON must contain no fields other than those named in `instruction.md`.

Evaluation note: the security audit executable lives under `/app/src`, and the verifier starts it with `cargo run --quiet` from `/app`.
