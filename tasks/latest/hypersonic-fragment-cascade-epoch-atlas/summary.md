# # Hypersonic fragment cascade epoch atlas

- **UUID:** `e55547a7-d339-42b6-9aff-6b6df8f29cc0`
- **Slug:** `hypersonic-fragment-cascade-epoch-atlas`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Build a Kessler-style orbital debris cascade forecasting system on the working TypeScript simulation library at /app. The system must ingest debris body catalogs, propagate Keplerian orbits with atmospheric drag under solar-flare density modulation, detect sphere-sphere collisions, spawn momentum-and-energy-conserving fragment clouds, and export a cascade fragment atlas with a collision epoch ledger.

All behavior, JSON field schemas, integrator constants, collision rules, drag model, hash conventions, and export contracts are defined in /app/docs/cli.md, /app/docs/staging-schema.md, /app/docs/kepler-integrator.md, /app/docs/collision-spawn.md, /app/docs/drag-flare.md, /app/docs/atlas-ledger-schema.md, /app/docs/export-sequence.md, and /app/docs/canonical-json-hash.md. Those documents govern every field name, array order, hash seal, and cross-artifact binding tested by the verifier.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
