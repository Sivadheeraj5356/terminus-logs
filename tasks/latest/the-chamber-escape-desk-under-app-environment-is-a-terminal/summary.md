# The chamber escape desk under /app/environment is a terminal puzzle simulation:

- **UUID:** `fe0f2689-b834-4534-93fe-fbe813b371f1`
- **Slug:** `the-chamber-escape-desk-under-app-environment-is-a-terminal`
- **Category:** games
- **Difficulty:** hard

## Summary

The chamber escape desk under /app/environment is a terminal puzzle simulation: a Rust pathfinding planner, a local topology HTTP service, graph fixtures under vault, and a public route-manifest contract. Operators at the escape desk run bash /app/environment/scripts/run_escape.sh to rebuild desk_k, start the hidden-port topology service, recover live chamber evidence, compute an egress walk through the vault graph, and write /app/output/route_manifest.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
