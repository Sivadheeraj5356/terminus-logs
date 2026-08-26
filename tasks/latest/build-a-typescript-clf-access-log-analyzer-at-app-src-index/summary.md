# Build a TypeScript CLF access-log analyzer at `/app/src/index.ts`. It must read

- **UUID:** `5dbdf19d-5703-4186-8c92-a9febbc98244`
- **Slug:** `build-a-typescript-clf-access-log-analyzer-at-app-src-index`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Build a TypeScript CLF access-log analyzer at `/app/src/index.ts`. It must read only regular `.log` files directly under `/app/logs`, ignore directories and symlinks, compile with the provided TypeScript config, and write `/app/report.json`.

Parse Combined Log Format lines with an IP, ident, user, timestamp, quoted request, status, bytes, quoted referer, and quoted user agent. Ignore empty or whitespace-only lines.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
