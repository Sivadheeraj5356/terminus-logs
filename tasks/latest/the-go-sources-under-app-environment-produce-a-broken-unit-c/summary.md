# The Go sources under `/app/environment` produce a broken unit-conversion graph.

- **UUID:** `0160b109-5123-40a9-b36e-388febc81d97`
- **Slug:** `the-go-sources-under-app-environment-produce-a-broken-unit-c`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Go sources under `/app/environment` produce a broken unit-conversion graph. Fixture arms never land a coherent ledger; diagnose against the docs and data, fix the sources, rebuild, and regenerate artifacts.

Hand-written outputs will not pass. Rebuild with `/app/environment/scripts/build_ucg.sh` after source edits.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
