# Organizational decision planning workflow

System-administration operators run a two-stage fleet planning workflow.

## Stage

`odip stage` loads a scenario directory containing `decisions.jsonl`, `units.json`, `dependencies.json`, `resources.json`, and `topology.json`, plus the shared policy file at `/app/fixtures/policies/approval_policy.json`. It writes `/app/state/odip/impact_lattice.json` with schema_version `odip.lattice.v1`.

The lattice must include: decision_ids (sorted), unit_ids (sorted), dependency_edges, impact_rows (decision_id → sorted affected unit_ids), resource_bookings, cycle_detected (bool), cycle_path (sorted node ids when cycle_detected), and lattice_digest (sha256 hex of the canonical lattice body excluding lattice_digest itself).

## Plan

`odip plan` reads only the lattice JSON and the approval policy. It must not reopen raw scenario JSONL files. It writes `/app/output/decision_impact_plan.json` with schema_version `odip.plan.v1`.

The plan must include: execution_order (topo-sorted decision ids), approval_steps, conflicts, regulatory_blocks, feasible (bool), and plan_digest.

## Run

`odip run` performs stage then plan in one invocation with the same contracts.


## Identifiers

Every lattice and plan carries scenario_id from meta.json. Bundled scenario directories under /app/fixtures/scenarios include dept_merge, vendor_replace, region_expand, budget_realloc, and program_cancel. Bundled region_expand decision R1 requires matching clearance when meta.required_clearance is set.
