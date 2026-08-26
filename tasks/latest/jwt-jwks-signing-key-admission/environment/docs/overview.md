# JWT JWKS signing-key admission overview

On JWT/JWKS trust boundaries, `mux` enforces signing-key admission for security
operators. Each realm under `/app/environment/fixtures` ships issuer, tenant,
and cache authorization tiers. Operators audit a realm; the admission path
applies those tiers, overlays durable companion state, enforces
generation-floor and deferred-retract revocation rules, and reseals epoch
metadata that key admission depends on so withdrawn kids stay denied.

Public surfaces:

- `/app/bin/mux audit --profile <name>`
- `/app/bin/mux pulse <name>` (advisory; not an admission decision)
- `/app/output/freshness-report.json`
- `/app/output/state/<profile>/` companion journals and `epoch.json`
- public layout manifest (`runtime/layout.json`)

The normative JWT/JWKS authorization specification lives in `docs/contract.md`.
Implement admission behavior from that specification; do not treat the
advisory pulse probe as proof that withdrawn signing kids stay denied.
