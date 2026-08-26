Correct and finish the Node.js simulator in `/app/src` so `node /app/src/cli.js --config <absolute-json-path> --out <absolute-directory>` produces reproducible thermal-cycle reports for a layered composite panel. The full config schema, update rules, and output schemas are in `/app/docs/thermal-cycle-contract.md`. Treat that file as the source of truth.

The command must accept `--config` and `--out` exactly once, both with absolute paths. On success it should replace the output directory with exactly `field.csv`, `events.csv`, `summary.json`, `trace.csv`, `material_profile.csv`, and `stability.csv`. Bad arguments or bad config must fail before touching the requested output directory, while later runtime failures should leave any existing output intact.

Keep the implementation general for the supplied configs and similar valid configs. Unknown config fields can be ignored, but do not invent extra validation beyond the contract.
