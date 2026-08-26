# Operate the local host firewall policy controller in `/app`. It does not converg

- **UUID:** `5d25f049-36d8-444d-9950-92ca6a6eb5a8`
- **Slug:** `operate-the-local-host-firewall-policy-controller-in-app-it`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Operate the local host firewall policy controller in `/app`. It does not converge after an interrupted apply, conflicting configuration drop-ins, or a restart with active runtime overrides.

Operators rely on `nxctl apply` and `nxctl recover` to reconcile durable controller state with the effective host policy and ownership model documented under `/app/docs`. Administrative convergence must satisfy layered configuration precedence, counter lineage across chain regeneration, crash recovery after partial staging, preservation of foreign operator rules, validation that rejects invalid effective policy without mutating durable state, accurate `nxctl status --json` reporting, and upgrade of supported legacy ownership manifests.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
