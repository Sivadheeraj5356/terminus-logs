# # Repair the offline DNSSEC publisher

- **UUID:** `13fcabe4-60f7-4f19-9e85-f4f6a333e23e`
- **Slug:** `repair-the-offline-dnssec-publisher`
- **Category:** security
- **Difficulty:** hard

## Summary

The offline publisher in `/app` produces inconsistent releases after interrupted DNSKEY rollovers and legacy snapshot imports. Repair the Go implementation shipped from environment sources into `/app`.

Static or hand-written output is not sufficient; `/output/example.test.signed` and `/output/publication-manifest.json` must be produced by the normal publish pipeline through `/app/bin/zonepub`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
