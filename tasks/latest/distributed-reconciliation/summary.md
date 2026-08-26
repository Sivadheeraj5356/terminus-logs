# distributed_reconciliation

- **UUID:** `6048e9db-9c3f-4f9e-8e46-d5071d783500`
- **Slug:** `distributed-reconciliation`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Update Go source under `/app/environment` to implement functions marked `// Stub:` in the coordination packages. The discrete-event driver (`/app/environment/internal/pipeline/run.go`), profile loader, fixture catalog, audit writer, metrics helpers, runner shell, bundled profiles, and offline verifier digest helpers are provided.

Complete stub packages per `/app/environment/docs/build_obligations.md` so bundled profiles produce `/app/output/schedule_audit.json` matching `/app/environment/docs/schedule_audit_schema.md`. The image is offline (`allow_internet = false`).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
