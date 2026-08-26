# An offline HAProxy edge load-balancer under `/app/environment` composes ACL and

- **UUID:** `0d35c7d1-a960-461c-ad58-1299f2e509cf`
- **Slug:** `an-offline-haproxy-edge-load-balancer-under-app-environment`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

An offline HAProxy edge load-balancer under `/app/environment` composes ACL and backend route plans, commits them as immutable generations behind a plan/commit token workflow, and records every commit in an append-only hash-chained ledger. The pipeline has drifted out of the contract documented under `/app/environment/docs`, so the regenerated audits and the durable state around them are no longer correct or consistent.

Bring the module behavior under `/app/environment` back onto the documented contract so the normal build-and-reload path produces conformant results: every matrix cell routed to its published backend target within the published row and group ceilings, refusal-marked cells left unrouted, byte-identical paired run digests, and the ledger, generations, registry, and the `status` and `verify` reports all consistent with one another. No outbound network access is available.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
