# The integer numerical RFIM simulation under `/app/environment` no longer reprodu

- **UUID:** `59dcaeee-a53a-4a49-8acb-2cec1019e392`
- **Slug:** `the-integer-numerical-rfim-simulation-under-app-environment`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The integer numerical RFIM simulation under `/app/environment` no longer reproduces the quasi-static hysteresis path across field intervals and resumed runs. Repair the Go numerical simulation source code under `/app/environment` so `go run /app/environment/cmd/fieldloop --model MODEL.json --field FIELD.tsv --output-dir DIR` evolves every reachable instability event, publishes `/app/output/trajectory.tsv`, `/app/output/avalanches.jsonl`, and `/app/output/checkpoint.json` by default, and follows the complete observable contract in `/app/environment/docs/FIELD_MODEL.rst`.

The bundled study uses `/app/environment/fixtures/model.json` and `/app/environment/fixtures/field.tsv`. Rebuild and regenerate the artifacts through the normal command; prewritten outputs are not a valid result.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
