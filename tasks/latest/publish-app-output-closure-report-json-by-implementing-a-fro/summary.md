# Publish `/app/output/closure_report.json` by implementing a from-scratch Go clos

- **UUID:** `8a1488a8-3662-4734-b3bf-c27d44be6dda`
- **Slug:** `publish-app-output-closure-report-json-by-implementing-a-fro`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Publish `/app/output/closure_report.json` by implementing a from-scratch Go closure merge engine, building `/app/bin/cl_publish` through `/app/scripts/compile_report.sh` or `/app/launcher/cl_publish`. The image ships tenant fragments, registry rows, runtime defaults, and consolidation docs under `/app/doc/` but no Go implementation sources.

Each publish must reload `/app/cfg/runtime.toml` and `/app/data/tenant_registry.json` from disk with no cross-run caching, including consecutive in-process invocations and tenants appended mid-session.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
