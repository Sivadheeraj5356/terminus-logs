# Security scope (bastion SSH access-control audit)

This task is a **security** exercise under the `security_authority_split` profile.
It is not a software-engineering feature implementation, debugging exercise, or
generic application refactor.

## Domain

Jump-host bastion access control: principals (human and service accounts),
allowed versus denied SSH directives, sudoers authorization fragments,
authorized-key posture, and least-privilege home-directory permissions on
staging bundles exported from production bastions.

## Authority boundary

- **Assets:** staged SSH/sudoers/home files, live Redis registry hashes, tenant overlays
- **Principals:** registry-backed users and service accounts with distinct grants
- **Allowed/denied actions:** handbook RULE tokens versus desk circulation drafts
- **Audit traces:** schema-valid `audit_report` and `fix_manifest` JSON with exit codes
- **Trust boundary:** live Redis reads must win over cache/archive shadow keys on the audit hot path

## Authoritative surfaces

- `/app/docs/bastion_access_handbook.md` — ratified authorization merge policy and amendments
- `/app/contracts/` — security audit and remediation trace schemas
- `/app/redis_fixtures/` — offline registry snapshots seeded into live Redis

Desk circulation sheets under `/app/docs/` are not authoritative.
