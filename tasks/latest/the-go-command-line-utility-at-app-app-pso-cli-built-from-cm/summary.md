# The Go command-line utility at `/app` (`/app/pso_cli` built from `./cmd/pso`) is

- **UUID:** `5fb99e55-805c-4031-92bc-f23ac00684ae`
- **Slug:** `the-go-command-line-utility-at-app-app-pso-cli-built-from-cm`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The Go command-line utility at `/app` (`/app/pso_cli` built from `./cmd/pso`) is a system administration utility designed for automated infrastructure configuration management and server parameter tuning across Linux clusters. Site reliability engineers (SREs) and system administrators invoke `/app/pso_cli` to tune multi-dimensional operating thresholds, service quotas, and kernel resource limits.

The CLI evaluates candidate server configurations using an internal parameter evaluation engine (`/app/internal/pso/pso.go`). However, the current engine implementation fails to enforce several critical operating boundary invariants, parameter step constraints, and configuration history formatting rules required by the infrastructure management suite.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
