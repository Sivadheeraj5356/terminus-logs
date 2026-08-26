# Symptom: after the monorepo migration the semantic version impact simulator unde

- **UUID:** `c7a7e66b-acc0-4938-80eb-4ed104febadb`
- **Slug:** `symptom-after-the-monorepo-migration-the-semantic-version-im`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

Symptom: after the monorepo migration the semantic version impact simulator under /app misreports how proposed upgrades propagate across twenty interconnected release graphs project_01 through project_20 in /app/release-graphs. The svis binary at /app/build/svis and report at /app/build/impact_report.json no longer match independent grading replay per independent_replay and verifier_rules.

Repair only /app/impact-engine/main.go, /app/propagation/semver/compare.go, and /app/propagation/simulate/propagate.go. Do not modify /app/Makefile, /app/go.mod, /app/semver-spec, /app/release-graphs, /app/probe-scripts, /app/contracts, or /opt/svis-fixtures.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
