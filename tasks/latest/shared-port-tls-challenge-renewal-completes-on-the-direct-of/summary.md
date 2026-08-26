# Shared-port TLS challenge renewal completes on the direct office path while the

- **UUID:** `276b23cf-80b5-47b8-a809-65710df50e49`
- **Slug:** `shared-port-tls-challenge-renewal-completes-on-the-direct-of`
- **Category:** security
- **Difficulty:** hard

## Summary

Shared-port TLS challenge renewal completes on the direct office path while the proxied vantage still reports mismatched ALPN negotiation and certificate material for the same hostname. Authoritative DNS validation and HTTP-01 remain disabled by policy; only the remaining challenge type may be used.

Fix sources under `/app/environment` so `/app/bin/run_lab` regenerates `/app/output/lab_observations.json` through the normal Rust pathlab driver. Static or hand-written observation JSON will not pass.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
