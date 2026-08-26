# The cryogenic LNG tank boil-off mass-balance assay under /app must compute heat-

- **UUID:** `dd6bfdff-def0-49e3-bcc9-6fdf76f700d5`
- **Slug:** `the-cryogenic-lng-tank-boil-off-mass-balance-assay-under-app`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The cryogenic LNG tank boil-off mass-balance assay under /app must compute heat-leak evaporation from wetted-area heat influx, relief vent mass, and tank inventory mass conservation using the analytical contracts in /app/docs/input-schema.md, /app/docs/profiles.md, /app/docs/numeric-rounding.md, /app/docs/heat-leak-bog.md, /app/docs/inventory-balance.md, /app/docs/maintenance-exclusions.md, /app/docs/hash-contract.md, /app/docs/state-format.md, /app/docs/stage-export.md, /app/docs/action-catalog.md, /app/docs/output-schema.md, and /app/docs/directory-overrides.md. Run lng-boiloff-reconciler so it reads tank geometry, insulation profiles, cryogenic readings, transfers, and gauged inventories under /app/data, writes the durable heat-mass stage to /app/state/boiloff-stage.json, and writes /app/output/boiloff-report.json plus /app/output/corrective-actions.tsv.

Absolute path overrides BOILOFF_INPUT_DIR, BOILOFF_OUTPUT_DIR, and BOILOFF_STATE_DIR must work. Results must be deterministic: unchanged physics inputs keep the same stage hash, and any change to tank metadata, readings, transfers, inventory snapshots, maintenance windows, or boil-off profiles must refresh the staged mass balance.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
