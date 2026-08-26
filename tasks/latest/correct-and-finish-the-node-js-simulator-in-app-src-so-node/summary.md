# Correct and finish the Node.js simulator in `/app/src` so `node /app/src/cli.js

- **UUID:** `acbaea34-2ad7-45fb-bdf3-02e7023f1209`
- **Slug:** `correct-and-finish-the-node-js-simulator-in-app-src-so-node`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Correct and finish the Node.js simulator in `/app/src` so `node /app/src/cli.js --config <absolute-json-path> --out <absolute-directory>` produces reproducible thermal-cycle reports for a layered composite panel. The full config schema, update rules, and output schemas are in `/app/docs/thermal-cycle-contract.md`.

Treat that file as the source of truth. The command must accept `--config` and `--out` exactly once, both with absolute paths.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
