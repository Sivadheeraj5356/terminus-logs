# Finish the Go CLI at `/app/cmd/depotlock/main.go` for release engineers who need

- **UUID:** `c6bfce8d-e3a0-4e92-b579-e06768d28f3d`
- **Slug:** `finish-the-go-cli-at-app-cmd-depotlock-main-go-for-release-e`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Finish the Go CLI at `/app/cmd/depotlock/main.go` for release engineers who need reproducible lock plans from an offline package index. From `/app`, invoke it as `go run /app/cmd/depotlock --index /app/fixtures/public/index.json --project /app/fixtures/public/project.json --out /app/lock-report.json`; all three flag values are replaceable absolute paths, not fixed inputs.

The contract at `/app/docs/resolver_contract.md` is authoritative for the input schema and declarative resolution rules. Implement every documented interaction among semantic-version constraints, default and requested features, optional and guarded dependencies, targets, patches, yanked releases, incompatibilities, cycles, repeated roots, and canonical assignment preference.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
