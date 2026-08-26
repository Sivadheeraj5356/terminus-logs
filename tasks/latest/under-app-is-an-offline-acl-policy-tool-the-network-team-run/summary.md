# Under /app is an offline ACL policy tool the network team runs before pushing a

- **UUID:** `4392a04d-f53b-4a81-aa36-76e5c25519e0`
- **Slug:** `under-app-is-an-offline-acl-policy-tool-the-network-team-run`
- **Category:** security
- **Difficulty:** hard

## Summary

Under /app is an offline ACL policy tool the network team runs before pushing a firewall change. It's a Go module for an `acl` binary with two JSON-printing subcommands, and neither is finished.

`acl evaluate --rules <path> --flows <path>` walks the observed flows and decides allow or deny for each, recording every log rule crossed before the terminal rule, plus a summary. `acl lint --rules <path> [--flows <path>]` audits the ruleset itself.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
