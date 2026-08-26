# Bastion SSH access-control security audit

Security task (`security_authority_split`): enforce least-privilege jump-host posture for Redis-authoritative bastion principals. Staging at `/app/staging/bundle.tar.gz` has drifted SSH directives, sudoers grants, and home-directory permissions relative to the live access registry.

Ratified authorization merge policy — principals, allowed SSH keys, sudoers fragments, `sshd_config.d` posture, and the trust boundary between live registry reads versus archive/cache shadows — lives in `/app/docs/bastion_access_handbook.md`. See `/app/docs/SECURITY_SCOPE.md` for task classification. Audit and remediation trace schemas are under `/app/contracts/`. Desk circulation drafts under `/app/docs/` are not authoritative.

The access-control entrypoint at `/app/bastion_cli` materializes the bundle, queries live Redis, and emits security audit or remediation outputs per `/app/contracts/audit_report_schema.md`, `/app/contracts/fix_manifest_schema.md`, and `/app/contracts/registry_schema.md`.

## Commands

Audit: `node /app/bastion_cli/src/cli.mjs audit --staging <dir> --bundle <tar.gz> --tenant <name> --report <path>`
Remediation: `node /app/bastion_cli/src/cli.mjs repair` with the same flags plus `--manifest <path>`.

## Behavioral contract

Registry merges tenant overlays onto global hashes with tenant leaves winning per field. Audit reports include `staging_root`, `tenant`, sorted `violations`, and `clean`. Remediation manifests include sorted `changes` with per-file digests, `noop`, and `manifest_sha256` per contract schema. Mode-only directory chmod corrections must not appear in `changes`. Live Redis fixtures under `/app/redis_fixtures/` are authoritative; cache snapshots and archive key aliases are not.
