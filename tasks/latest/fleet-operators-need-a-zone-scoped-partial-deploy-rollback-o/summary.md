# Fleet operators need a zone-scoped partial-deploy rollback orchestrator on the w

- **UUID:** `8f73900d-c0c6-41d8-b6fd-f107cd4e1e14`
- **Slug:** `fleet-operators-need-a-zone-scoped-partial-deploy-rollback-o`
- **Category:** system-administration
- **Difficulty:** medium

## Summary

Fleet operators need a zone-scoped partial-deploy rollback orchestrator on the working baseline under /app. Build it so rollbackctl at /app/bin/rollbackctl can capture release truth into midpipe under /app/state and publish a dependency-safe rollback wave at /app/output/rollback-plan.json with seal binding.

It validates witness quorum for the primary zone and coordinates apply through /app/deploy/scripts/apply-rollback.sh when operators invoke it. The bundled incident in /app/data/deploy/release-state.json covers ledger-db, identity-gate, billing-core, and alert-dispatch for release rel-8821.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
