# The incident-response team needs the endpoint quarantine decision gate in `/app`

- **UUID:** `5e0e87a7-9e41-486d-ae19-81032b052d1e`
- **Slug:** `the-incident-response-team-needs-the-endpoint-quarantine-dec`
- **Category:** security
- **Difficulty:** hard

## Summary

The incident-response team needs the endpoint quarantine decision gate in `/app` completed before the next SOAR drill. The gate reviews a proposed containment bundle, applies the quarantine approval policy, and emits the exact decision JSON imported by the response workflow.

Implement the `/app/quarantine-plan` command in Go. The verifier builds it from the module already present in `/app` and invokes:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
