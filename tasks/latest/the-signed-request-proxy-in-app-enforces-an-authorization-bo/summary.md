# The signed-request proxy in `/app` enforces an authorization boundary between HM

- **UUID:** `90013102-c160-4394-9385-a4968e9e9165`
- **Slug:** `the-signed-request-proxy-in-app-enforces-an-authorization-bo`
- **Category:** security
- **Difficulty:** hard

## Summary

The signed-request proxy in `/app` enforces an authorization boundary between HMAC verification and backend forwarding. `/app/bin/proxy-local` must authorize and forward the same semantic request for live traffic and for requests recovered from `/app/state/spool`.

Align the implementation with the profiles and recovery rules in `/app/docs/request-semantics.md`: valid current and legacy signatures remain accepted, invalid or ambiguous requests are rejected before forwarding, and duplicate or connection-nominated headers, encoded paths and queries, transfer framing, body limits, key/profile epochs, rotation, revocation, and restart recovery produce the documented backend request and decision. Keep the existing local-only CLI and streaming limits.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
