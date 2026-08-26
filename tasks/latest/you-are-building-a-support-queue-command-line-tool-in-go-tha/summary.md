# You are building a support-queue command line tool in Go that manages a SQLite d

- **UUID:** `bdf62428-3f1a-4029-9cea-2ae2fff7ae43`
- **Slug:** `you-are-building-a-support-queue-command-line-tool-in-go-tha`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

You are building a support-queue command line tool in Go that manages a SQLite database of support agents, tickets, resolutions, and an HMAC-secured audit chain. The binary lives at /app/app and every command takes the database path as its first argument, followed by any command-specific arguments.

Full command signatures live in /docs/API_SPEC.md, the table layout is in /docs/schema.md, exact error strings are in /docs/error-codes.md, chain rules live in /docs/chain-spec.md, statistical formulas live in /docs/statistics-spec.md, and the integrity-check rules live in /docs/lint-spec.md. Treat those files as the source of truth for anything not covered here.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
