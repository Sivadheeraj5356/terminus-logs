# Linux PAM faillock authentication lab

The controller under `/app` enforces PAM-style failed-login account lockout for
credential-stuffing defense across a host management view and a separated
user-namespace privilege boundary. Lockout denials, unlock clears, and
authentication enforcement audits must keep namespace privilege boundaries
aligned with host-side access control.

Access-control rules live under `/app/docs/` (`lock_rules.md`, `lock_contract.md`).
Auth-store and durable evidence live under `/app/state/`. Lockout attack
scenarios and failed-login records live under `/app/data/`.

The graded access-control binary is `/app/bin/bayctl`. Rebuild after source changes:

```bash
go build -o /app/bin/bayctl /app/cmd/bayctl
```

`GONOSUMDB='*'` and `GOFLAGS='-mod=mod'` are accepted when module checksum
lookup is unavailable in the container.
