# Bastion staging layout

Runtime tree under `/app`:

- `bastion_cli/` — bastion access-control audit entrypoint (`node /app/bastion_cli/src/cli.mjs`)
- `staging/bundle.tar.gz` — drifted SSH/sudoers/systemd/home archive
- `redis_fixtures/` — access registry documents loaded by `scripts/seed_redis.mjs`
- `contracts/` — security audit report, remediation manifest, and registry schemas
- `docs/` — bastion access handbook, SECURITY_SCOPE, and desk drafts
- `scripts/bastion-run` — starts Redis and seeds fixtures

Contracts in `/app/contracts/` define authorization merge semantics, violation kinds, and idempotent remediation manifests.
