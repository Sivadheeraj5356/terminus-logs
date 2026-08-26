# Resource feasibility and regulatory contract

## Resources

`resources.json` entries: `{ "pool": "...", "decision_id": "...", "start": <int>, "end": <int> }` with half-open windows `[start, end)`.

Two bookings conflict when they share the same pool and windows overlap (`a.start < b.end && b.start < a.end`) and decision_ids differ. Emit conflict objects `{ "type": "resource", "pool", "decision_a", "decision_b" }` with decision_a < decision_b lexicographically. Sort conflicts by type, pool, decision_a, decision_b.

## Timeline exclusive units

If two decisions both mark `"exclusive": true` and share any affected unit after fan-out and their `window` objects overlap (`window.start`/`window.end` half-open), emit `{ "type": "timeline", "unit", "decision_a", "decision_b" }` with decision_a < decision_b. Sort after resource conflicts using the same key order with unit substituted for pool.

## Regulatory

Decisions with class `region_expand` require `"clearance": "<token>"` matching `required_clearance` in the scenario `meta.json`. Missing or mismatched clearance yields `{ "type": "regulatory", "decision_id", "reason": "clearance_missing" }` in regulatory_blocks and sets feasible false.

## Feasible

`feasible` is false when cycle_detected, any conflict exists, or any regulatory_block exists. Otherwise true.
