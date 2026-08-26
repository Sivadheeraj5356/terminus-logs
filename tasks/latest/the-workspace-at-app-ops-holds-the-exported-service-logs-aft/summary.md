# The workspace at /app/ops holds the exported service logs after the service was

- **UUID:** `cbca50ee-8019-4428-9c4d-8a403a0d2494`
- **Slug:** `the-workspace-at-app-ops-holds-the-exported-service-logs-aft`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The workspace at /app/ops holds the exported service logs after the service was rotated, reloaded, rolled back in one partition window, and exported again. Reconcile the operational authorities so export --root /app/ops --out /app/output/current produces a signed compliance bundle whose report reflects the final partition set, cursor lineage, and omission ledger.

Read /app/environment/docs/contract.md, cursor_trace.md, ledger.md, manifest.md, and commands.md. They cover the event trace, SQLite checkpoint columns, manifest fields, digest formulas, acceptable terminal states, legacy v1 compatibility, and the export/verify commands.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
