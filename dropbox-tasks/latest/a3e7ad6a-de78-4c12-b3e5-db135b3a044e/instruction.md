Operations engineers coordinating multi-unit fleet config rollouts need an operational planning workflow that stages an impact lattice and delivers an ordered feasibility plan before daemon rollout windows open. The Go workspace under /app already loads scenario fixtures and builds the odip binary. Extend that baseline so operators can run stage, plan, and run against scenario directories and the shared approval policy file /app/fixtures/policies/approval_policy.json


Stage must write the lattice artifact to /app/state/odip/impact_lattice.json before plan runs. Plan must write the feasibility plan to /app/output/decision_impact_plan.json and, on success, append one journal line to /app/state/odip/rollout_journal.jsonl without reopening raw scenario decision files. Plan must consume the staged lattice and policy only. Each artifact must carry the scenario identity from that scenario meta file. Lattice digests are lowercase hex witnesses of the staged fleet snapshot. Plans bind epoch seals, window digests, and booking digests, refuse superseded epochs with exit code 4, and surface topology fan-out, dependency cycles, pool contention, exclusive-window drift, approval stacking, and regional clearance failures as infeasible or conflicted rollouts.

CLI surface is /app/bin/odip with stage, plan, and run. Bundled scenarios live under /app/fixtures/scenarios (including dept_merge and vendor_replace among others). Additional packs may appear under /opt/verifier-fixtures with the same directory layout.

Field schemas, ordering rules, seal formulas, and pack catalogs are reference material in:

/app/docs/org-decision-planning-workflow.md
/app/docs/dependency-closure-contract.md
/app/docs/impact-propagation-contract.md
/app/docs/approval-gate-contract.md
/app/docs/resource-feasibility-contract.md
/app/docs/fleet-rollout-ops.md
/app/docs/odip-operator-commands.md
/app/docs/rollout-epoch-seal-contract.md
/app/docs/booking-window-slot-contract.md
/app/docs/holdout-probe-fixtures.md
