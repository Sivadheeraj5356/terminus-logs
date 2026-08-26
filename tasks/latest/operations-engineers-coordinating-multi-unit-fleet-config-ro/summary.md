# Operations engineers coordinating multi-unit fleet config rollouts need an opera

- **UUID:** `a3e7ad6a-de78-4c12-b3e5-db135b3a044e`
- **Slug:** `operations-engineers-coordinating-multi-unit-fleet-config-ro`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Operations engineers coordinating multi-unit fleet config rollouts need an operational planning workflow that stages an impact lattice and delivers an ordered feasibility plan before daemon rollout windows open. The Go workspace under /app already loads scenario fixtures and builds the odip binary.

Extend that baseline so operators can run stage, plan, and run against scenario directories and the shared approval policy file /app/fixtures/policies/approval_policy.json Stage must write the lattice artifact to /app/state/odip/impact_lattice.json before plan runs. Plan must write the feasibility plan to /app/output/decision_impact_plan.json and, on success, append one journal line to /app/state/odip/rollout_journal.jsonl without reopening raw scenario decision files.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
