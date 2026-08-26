# The backup utility under `/app` manages five labs. A maintenance window left the

- **UUID:** `d20e9a96-92ec-43d5-8935-b126b122c9c0`
- **Slug:** `the-backup-utility-under-app-manages-five-labs-a-maintenance`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The backup utility under `/app` manages five labs. A maintenance window left the system unable to complete its `fieldday-2026-06-18` restore drill — the tool exits with errors and produces no output.

The operational state of the data layer was disrupted by the maintenance. Documentation under `/app/docs/` describes the storage layout and output contracts.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
