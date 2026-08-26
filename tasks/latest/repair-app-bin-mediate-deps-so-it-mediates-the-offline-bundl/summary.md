# Repair `/app/bin/mediate-deps` so it mediates the offline bundle in `/app/data`

- **UUID:** `1fe5cff0-5933-4d47-8274-1dfc9e9f8211`
- **Slug:** `repair-app-bin-mediate-deps-so-it-mediates-the-offline-bundl`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Repair `/app/bin/mediate-deps` so it mediates the offline bundle in `/app/data` and writes `audit.json`, `classpath.csv`, `mediation.csv`, and `findings.csv` as documented in `/app/README.md`. Use only local files under `/app`; no network access.

The Clojure engine in `/app/src/indigo/` resolves the default bundle but does not fully implement every rule in `/app/mediation-policy.md`. Validate against both `/app/data` and the focused bundles under `/app/examples/` (including `nearest-tie/` and `topo-order/`); a zero-exit run on `/app/data` alone is not sufficient.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
