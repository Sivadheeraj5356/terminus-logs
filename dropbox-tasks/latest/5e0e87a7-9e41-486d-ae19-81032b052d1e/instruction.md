The incident-response team needs the endpoint quarantine decision gate in `/app` completed before the next SOAR drill. The gate reviews a proposed containment bundle, applies the quarantine approval policy, and emits the exact decision JSON imported by the response workflow.

Implement the `/app/quarantine-plan` command in Go. The verifier builds it from the module already present in `/app` and invokes:

`/app/quarantine-plan --bundle /absolute/path/to/bundle.json --out /absolute/path/to/decision.json`

Use `/app/containment/bundle.json` as the public incident fixture. The full quarantine approval policy is in `/app/containment/QUARANTINE_POLICY.md`; treat it as authoritative for asset eligibility, action usability, confidence coverage, cross-action requirements, reviewer/owner limits, escalation approval, winner selection, and tie-breaking.

The output file must be UTF-8 JSON with exactly these top-level fields in this order: `status`, `winner`, `selected_actions`, `risk_score`, `review_minutes`, `outage_units`, `rule_slots`, `selected_owners`, and `assets`.

Each row in `assets` must preserve input asset order and use exactly these fields in this order: `asset_id`, `status`, `selected_actions`, `risk_score`, `review_minutes`, `outage_units`, `rule_slots`, `selected_owners`, and `reasons`.

Hidden incident bundles may contain many locally plausible containment actions for a single endpoint. The planner must remain responsive by using the policy limits, dependency/conflict rules, confidence coverage, owner caps, and canonical comparison rules to discard losing or impossible plans early. Exact JSON formatting whitespace is not important, but arrays, nulls, field order, statuses, selected action ids, owner lists, reasons, and numeric totals must match the policy result exactly.
