# Bastion Access Control Handbook

Version 3.2 — Platform Security Engineering (internal)

## Purpose

This document records the **security authority split** for the Redis-backed bastion access registry and the access-control audit entrypoint that enforces SSH staging bundles exported from jump hosts. External JSON contracts under `/app/contracts/` define verifier-visible security audit traces; this handbook records merge semantics and ratified machine-readable RULE tokens.

## Registry authority

Live Redis hashes seeded from `/app/redis_fixtures/` are authoritative at runtime. The audit entrypoint must query Redis on every audit or remediation invocation — static fixture files and hardcoded user lists are not substitutes. Desk circulation sheets such as `/app/docs/access_desk.md` are drafts only and must not override ratified handbook RULE lines.

Key layout is specified in `/app/contracts/registry_schema.md`.

## Staging bundle conventions

Bundles are gzip-compressed tar archives copied to `<staging>/bundle.tar.gz`. Extraction targets `<staging>/extracted/` and must preserve archive-relative paths, including the `homes/` directory prefix (for example `homes/alice/.ssh/authorized_keys`). Stripping the first path segment or flattening home directories breaks downstream mode and key checks.

Re-extraction must be idempotent: once a bundle has been extracted for a staging directory, later audit or repair invocations operate on the existing tree rather than wiping repaired files.

## Tenant overlays

Per-tenant override hashes live at `bastion:overrides:tenant:{tenant}`. The `sshd_settings` field holds JSON describing relative `sshd_config.d` paths mapped to directive objects. Effective sshd settings **deep-merge** tenant directive maps onto global `bastion:sshd_settings` entries; tenant leaves win per directive key. Assigning the overlay blob to a scalar field or shallow-spreading the overlay hash over global mode maps is incorrect.

The `staging` tenant exists for pre-production validation with stricter sshd posture than `prod`. The `canary` tenant supports preflight promotion checks; the `dr` tenant supports disaster-recovery bundle validation; the `edge` tenant supports edge-region promotion gates; the `vault` tenant supports vault-region bundle validation; the `atlas` tenant supports atlas-region sshd gates; the `comet` tenant supports comet preflight bundles; the `orbit` tenant supports orbit-region validation; the `pulse` tenant supports pulse-region cipher posture checks. Use the matching `--tenant` flag — do not assume prod overlay semantics apply to other tenants.

## Registry cache documents

Operational snapshots at `bastion:registry:cache:{tenant}` are DR read-only references. Audit and remediation must read live production hashes and tenant overlays, not cache documents.

## Permission and sudoers policy

File modes in `bastion:file_modes` are octal strings. Comparisons normalize by stripping leading zeros and left-padding to four digits (`750` equals `0750`).

`bastion:service_accounts` lists deploy principals allowed in sudoers. Registry lines missing from staged sudoers are `sudoers_missing` violations. Staged principals ending in `-deploy` that are absent from the service account set are `sudoers_unauthorized`. Unauthorized sudoers must be reported on audit even when desk circulation sheets suggest skipping that check.

Repaired `sudoers.d/bastion-users` must emit lines in `bastion:sudoers_lines` hash field order — not alphabetically by principal name.

## Audit and remediation outputs

Audit reports follow `/app/contracts/audit_report_schema.md` (`staging_root`, `tenant`, sorted `violations`, `clean`). Repair manifests follow `/app/contracts/fix_manifest_schema.md` (`staging_root`, `tenant`, sorted `changes`, `noop`, `manifest_sha256`). Each change records `path`, `before_sha256`, and `after_sha256` content digests for a rewritten **file** whose bytes changed. Mode-only `chmod` repairs on directories (for example `homes/alice/.ssh`) are applied silently and must not appear in `changes`.

A second repair on an already-clean tree must emit `noop: true`, an empty `changes` array, and a stable digest computed over that empty sorted array.

## Ratified amendments

RULE tokens below are parsed by the policy bridge. When duplicate keys appear, **later amendments win**. Archival copies may contain a `circulation draft — superseded` marker; RULE lines above that marker in such copies are ignored.

### Amendment 2024-09 — baseline registry

RULE:REGISTRY_SOURCE=handbook_last_wins
RULE:USERS_KEY=bastion:users
RULE:TENANT_OVERLAY_PREFIX=bastion:overrides:tenant:
RULE:SSH_KEYS_KEY=bastion:ssh_keys
RULE:MODE_COMPARE=octal_normalized
RULE:MERGE_STRATEGY=redis_tenant_last_wins
RULE:ARCHIVE_STRIP_PREFIX=preserve_relative
RULE:ACTIVE_PACKET=BASELINE-2024-09

### Amendment 2025-01 — staging tenant

RULE:STAGING_TENANT=staging

Pre-production bundles validated with `--tenant staging` use the staging overlay hash for sshd deep-merge.

### Amendment 2025-03 — repair manifest digest

`manifest_sha256` is the lowercase hexadecimal SHA-256 of the UTF-8 encoding of **only** the `changes` array after sorting entries by ascending `path`, serialized as compact JSON with no insignificant whitespace (`JSON.stringify` default). Do **not** hash the full manifest object, pretty-printed JSON, or unsorted change lists.

RULE:MANIFEST_HASH_SCOPE=changes_array_compact

### Amendment 2025-04 — canary and dr tenants

RULE:CANARY_TENANT=canary
RULE:DR_TENANT=dr

Canary preflight and disaster-recovery bundles use `--tenant canary` or `--tenant dr` with tenant-specific overlay merges.

### Amendment 2025-05 — registry cache prohibition

RULE:REGISTRY_CACHE_POLICY=live_hashes_only

### Amendment 2025-06 — edge and vault tenants

RULE:EDGE_TENANT=edge
RULE:VAULT_TENANT=vault

Edge-region and vault-region bundles use `--tenant edge` or `--tenant vault` with tenant-specific overlay merges.

### Amendment 2025-07 — sudoers emission order

RULE:SUDOERS_ORDER=registry_hash_field_order

Repaired sudoers fragments preserve `bastion:sudoers_lines` hash field order; alphabetical principal sorting is incorrect.

### Amendment 2025-08 — atlas and comet tenants

RULE:ATLAS_TENANT=atlas
RULE:COMET_TENANT=comet

Atlas-region and comet preflight bundles use `--tenant atlas` or `--tenant comet` with tenant-specific overlay merges.

### Amendment 2025-09 — orbit and pulse tenants

RULE:ORBIT_TENANT=orbit
RULE:PULSE_TENANT=pulse

Orbit-region and pulse-region bundles use `--tenant orbit` or `--tenant pulse` with tenant-specific overlay merges.

### Amendment 2025-10 — manifest changes scope

`changes` lists only file content rewrites. Mode-only directory repairs from `bastion:file_modes` must not produce change entries; distinct `before_sha256` and `after_sha256` digests are required for every listed change.

RULE:MANIFEST_CHANGES_SCOPE=content_rewrite_only

### Amendment 2025-11 — eclipse and nebula tenants

RULE:ECLIPSE_TENANT=eclipse
RULE:NEBULA_TENANT=nebula

Eclipse-region and nebula-region bundles use `--tenant eclipse` or `--tenant nebula` with tenant-specific overlay merges.

### Amendment 2025-12 — solstice and pulsar tenants

RULE:SOLSTICE_TENANT=solstice
RULE:PULSAR_TENANT=pulsar

Solstice preflight and pulsar edge bundles use `--tenant solstice` or `--tenant pulsar` with tenant-specific overlay merges.

## Background

Jump-host SSH posture is enforced through registry-backed authorized keys, sudoers fragments, and `sshd_config.d` drop-ins. The access-control audit tooling replaced manual diff scripts in 2024-Q4 after repeated staging promotion incidents. Redis fixtures mirror production snapshots for offline evaluation environments.

### Amendment 2025-13 — zenith and lumen tenants

RULE:ZENITH_TENANT=zenith
RULE:LUMEN_TENANT=lumen

Zenith-region and lumen preflight bundles use `--tenant zenith` or `--tenant lumen` with tenant-specific overlay merges.

### Amendment 2025-14 — cobalt and vector tenants

RULE:COBALT_TENANT=cobalt
RULE:VECTOR_TENANT=vector

Cobalt-region and vector edge bundles use `--tenant cobalt` or `--tenant vector` with tenant-specific overlay merges.

### Amendment 2025-15 — horizon and flux tenants

RULE:HORIZON_TENANT=horizon
RULE:FLUX_TENANT=flux

Horizon-region and flux preflight bundles use `--tenant horizon` or `--tenant flux` with tenant-specific overlay merges.

### Amendment 2025-16 — apex and relay tenants

RULE:APEX_TENANT=apex
RULE:RELAY_TENANT=relay

Apex-region and relay edge bundles use `--tenant apex` or `--tenant relay` with tenant-specific overlay merges.

Repair pipelines must apply every `bastion:file_modes` registry path including `homes/*/.ssh` directories and `authorized_keys` files even when those paths are excluded from manifest `changes` per Amendment 2025-10.

### Amendment 2025-17 — spire and nova tenants

RULE:SPIRE_TENANT=spire
RULE:NOVA_TENANT=nova

Spire-region and nova preflight bundles use `--tenant spire` or `--tenant nova` with tenant-specific overlay merges.

### Amendment 2025-18 — titan and forge tenants

RULE:TITAN_TENANT=titan
RULE:FORGE_TENANT=forge

Titan-region and forge edge bundles use `--tenant titan` or `--tenant forge` with tenant-specific overlay merges.

Repair must apply every `bastion:file_modes` path before returning; audit `clean` must be true only when modes keys authorized_keys sshd and sudoers violations are all absent simultaneously.

### Amendment 2025-19 — ember and onyx tenants

RULE:EMBER_TENANT=ember
RULE:ONYX_TENANT=onyx

Ember and onyx regional bundles use `--tenant ember` or `--tenant onyx` with tenant-specific overlay merges.

### Amendment 2025-20 — sentinel and cipher tenants

RULE:SENTINEL_TENANT=sentinel
RULE:CIPHER_TENANT=cipher

Sentinel and cipher edge bundles use `--tenant sentinel` or `--tenant cipher` with tenant-specific overlay merges.

Repair must apply every `bastion:file_modes` path before returning; audit `clean` must be true only when modes keys authorized_keys sshd and sudoers violations are all absent simultaneously.

### Amendment 2025-21 — bundle extraction idempotency

RULE:EXTRACT_MARKER=.bastion_extracted
RULE:EXTRACT_POLICY=skip_when_marker_present

After the first successful bundle extraction into `extracted/`, write marker file
`.bastion_extracted` containing the bundle path. Subsequent `audit` or `repair`
invocations on the same staging tree must not re-extract when the marker exists,
so repaired files survive repair-then-audit sequences.

### Amendment 2025-22 — sshd deep merge baseline

RULE:SSHD_MERGE=deep_per_directive_global_base

Tenant `bastion:overrides:tenant:{tenant}` sshd_settings JSON merges directive-by-directive
onto global `bastion:sshd_settings` maps per path. Repairs must preserve global directives
not overridden by the tenant overlay (for example `PermitRootLogin` and `PasswordAuthentication`
on tenants that only override `AllowUsers`).

### Amendment 2025-23 — audit exit codes

RULE:AUDIT_EXIT_CLEAN=0
RULE:AUDIT_EXIT_DIRTY=3

`audit` exits 0 when the report `clean` field is true and 3 when violations remain.

### Amendment 2025-24 — quartz and obsidian tenants

RULE:QUARTZ_TENANT=quartz
RULE:OBSIDIAN_TENANT=obsidian

### Amendment 2025-25 — garnet and slate tenants

RULE:GARNET_TENANT=garnet
RULE:SLATE_TENANT=slate

### Amendment 2025-26 — crimson and jade tenants

RULE:CRIMSON_TENANT=crimson
RULE:JADE_TENANT=jade

### Amendment 2025-27 — opal and ivory tenants

RULE:OPAL_TENANT=opal
RULE:IVORY_TENANT=ivory

### Amendment 2025-28 — manifest change path normalization

RULE:MANIFEST_PATHS=relative_no_leading_dot_slash

Manifest `changes[].path` values must be relative to `staging_root` without a leading `./` prefix.
