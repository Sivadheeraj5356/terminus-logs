# A Go parcel access-control gateway lives under /app/environment. It reads untrus

- **UUID:** `90f2a905-eb44-4c77-9805-2ed92f74162a`
- **Slug:** `a-go-parcel-access-control-gateway-lives-under-app-environme`
- **Category:** security
- **Difficulty:** unknown

## Summary

A Go parcel access-control gateway lives under /app/environment. It reads untrusted parcel-routing scripts and must emit exact allow or deny security decisions for each valid request record.

Bring the gateway into conformance with the security contract in /app/environment/docs/ACCESS_CONTRACT.md. The contract covers field-count validation, ignored malformed records, generated route policies, checkpoints, replay behavior, overlays, seals, leases, rates, budgets, TTL aging, sequenced request-id binding, and rollback after denials.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
