# # Recover the authoritative DNS release service

- **UUID:** `baebd414-2e04-43ac-9fa9-71f70cc9403e`
- **Slug:** `recover-the-authoritative-dns-release-service`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The failed change window left the Harbor authoritative DNS service without a releasable configuration. Recover it from the incident evidence in `/app/evidence` and leave a production-shaped BIND configuration that operators can validate and start.

This is a system-administration task: do not build a parser, reconciler, or other custom program. Do not modify anything under `/app/evidence`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
