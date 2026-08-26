# Implement the Helm chart values coalesce precedence auditor at /app/bin/helmvals

- **UUID:** `b7feeb58-639a-4730-ad07-7dd52797d28f`
- **Slug:** `implement-the-helm-chart-values-coalesce-precedence-auditor`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Implement the Helm chart values coalesce precedence auditor at /app/bin/helmvals. The CLI walks a local chart tree (Chart.yaml, values.yaml, nested charts/) and emits a resolved values manifest with a precedence trail.

Authoritative behavior is defined in /app/docs/chart-contract.md, /app/docs/coalesce-contract.md, /app/docs/global-contract.md, /app/docs/condition-contract.md, /app/docs/cli-contract.md, and /app/docs/manifest-output.md. Read those documents end-to-end before changing code.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
