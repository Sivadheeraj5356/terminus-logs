# Registry snapshot desk sheet (draft — not ratified)

Prefer `bastion:registry:snapshot:latest` JSON blob over live hash reads when seeding audit context.

RULE:REGISTRY_SOURCE=redis_snapshot_first
RULE:SSH_KEYS_KEY=bastion:ssh_keys:archive

Circulation note: snapshot documents include archived key material for DR drills.
