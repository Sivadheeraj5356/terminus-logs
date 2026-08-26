# EmbedServe production still ships the default inference profile with a static Ca

- **UUID:** `3f540f50-b76d-40a6-98d9-8d35b289e2ac`
- **Slug:** `embedserve-production-still-ships-the-default-inference-prof`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

EmbedServe production still ships the default inference profile with a static Cargo denylist and permissive model-loading defaults. The PHP hardening CLI under `/app/environment` has scaffolding for SQLite inventory lookups, operations-bundle policy extraction, and tokenizer-sidecar advisory scanning, but it does not yet drive a full harden run from live RustSec evidence.

Extend the CLI so profile `embedserve-default` (declared in `/app/environment/config/profiles.json`) is hardened through the normal pipeline:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
