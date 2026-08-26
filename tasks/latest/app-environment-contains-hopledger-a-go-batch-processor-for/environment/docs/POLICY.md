# Policy rules

Policy documents:

```json
{
  "default_sla_ms": 120,
  "rules": [
    {"pattern": "alpha>*", "sla_ms": 80},
    {"pattern": "*>omega", "sla_ms": 70},
    {"pattern": "alpha>omega", "sla_ms": 50}
  ]
}
```

Rules:

- No policy means `sla_ms = 0` and no alarm breaches.
- Supported patterns: exact `src>dst`, source wildcard `src>*`, destination wildcard `*>dst`, full wildcard `*>*`.
- Match precedence: exact, source wildcard, destination wildcard, full wildcard, default.
- Within the same precedence tier, the first rule in file order wins.
- `policy_update` replaces the active policy for subsequent events only.
- Each link row reports the SLA active at the final event touching that link.
- A hop breaches only when `ms > active_sla_ms` and `active_sla_ms > 0`.
- `policy_digest` is SHA-256 of the raw initial policy file bytes, or empty string when omitted.
- `policy_lineage_digest` is SHA-256 over canonical JSON for the initial policy plus every applied `policy_update`, in replay order.
