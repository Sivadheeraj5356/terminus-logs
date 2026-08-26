# AtlasBatch still promotes inference models by hand — someone eyeballs the Compos

- **UUID:** `66f7bc77-ca73-450c-8f41-c184ce26d473`
- **Slug:** `atlasbatch-still-promotes-inference-models-by-hand-someone-e`
- **Category:** data-processing
- **Difficulty:** medium

## Summary

AtlasBatch still promotes inference models by hand — someone eyeballs the Compose service, canary JSON, eval DB numbers, registry manifests, and whether the sklearn pin exists upstream. Wire up the Lua CLI at `/app/bin/atlas-promote` so `run --candidate <id> --compose <path>` evaluates every promotion gate and writes `/app/output/promotion-decision.json` per `/app/docs/promotion-decision.schema.json`.

Several modules under `/app/src/` regressed during a refactor, including shared helpers split out of the gate logic. Gate rules and input contracts are spread across `/app/docs/` and `/app/archives/`; ratified comms supersede legacy engineering notes.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
