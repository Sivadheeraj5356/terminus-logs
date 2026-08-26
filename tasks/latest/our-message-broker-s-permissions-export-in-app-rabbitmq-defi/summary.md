# Our message broker's permissions export in /app/rabbitmq_definitions.json

- **UUID:** `6e613bd6-685e-4b60-8c6f-971e419341e6`
- **Slug:** `our-message-broker-s-permissions-export-in-app-rabbitmq-defi`
- **Category:** security
- **Difficulty:** hard

## Summary

Our message broker's permissions export in /app/rabbitmq_definitions.json hasn't been reconciled since the last few access-review tickets, a recent incident's temporary access grant, and a security review. Bring the permissions array into compliance with /app/RABBITMQ_ACCESS_POLICY.md, cross-referencing /app/PERMISSION_CHANGELOG.md, /app/DOWNSTREAM_CONSUMERS.md, /app/PROTECTED_SERVICE_ACCOUNTS.md, and /app/INCIDENT_ACCESS.md to work out what the correct end state actually is right now.

Existing entries may be missing outright, over-granted, under-granted, or stale; the correct end state is whatever the policy and its reference documents imply, not just a correction of what's already there. The policy document explains how a user's capability on a resource is decided, which of the reference files can override the plain tier-based defaults and how, how a temporary grant's validity window is evaluated, and caps on how many accounts may hold each of the two most destructive capabilities across the confidential vhosts combined.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
