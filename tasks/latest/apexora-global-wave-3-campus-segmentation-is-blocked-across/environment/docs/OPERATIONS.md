# Wave 3 operations contract

The checked-in data, not a count reconstructed from edited files, defines the
rollout baseline:

- `inventory/device_inventory.yaml` is the exact authoritative 96-host
  hostname-to-`migration_state` map. Hostnames and states are immutable.
- `inventory/wave3_validation_scope.yaml` is the exact authoritative ordered
  48-host validation map. Hostnames, order, and the
  `dist-hq-dal-main-01` canary anchor are immutable.
- The authoritative VLAN catalog is exactly every integer ID from 2001 through
  2180 inclusive (180 IDs). VLAN IDs 101 through 180 are retired.

## Transitive dependency spine

Wave 3 is validated as one dependency graph. Later stages consume earlier
resolution and stage artifacts. An incorrect upstream decision must surface in
downstream exports.

Binding stage order (`scripts/run-netsegctl.sh all`):

```text
vlan-check → trunk-check → acl-check → render → wave-plan → rollback-audit → evidence
```

### 1. Canonical VLANs (vlan-check)

`canonical_ids` is the intersection of four public sources:

1. Operations range `[2001, 2180]` (this document)
2. `vlans/catalog.yaml` VLAN `id` values
3. Union of `vlans/campuses/*.yaml` VLAN `id` values
4. Consistency against `vlans/legacy_id_map.yaml`:
   - every catalog `legacy_id` is a map key
   - every map target is inside `canonical_ids`
   - campus union equals the catalog id set

`vlan_catalog_count` is `len(canonical_ids)`. Source drift yields
`vlan_source_drift` violations. Access ports must use only `canonical_ids`.

### 2. Resolved VRFs (feeds ACL)

For each region in `amer`, `emea`, `apac`:

```text
resolved_vrfs(region) =
  keys(vrfs/catalog.yaml) ∩ route-target VRF names in
  vrfs/campus_route_targets/<region>.yaml
```

Campus→region comes from `inventory/campus_index.yaml`. WAN-edge devices must
not retain `VRF-CORP`; the canonical WAN VRF is `CORP-IT`, which must appear in
`resolved_vrfs(region(device))`.

### 3. Allowed ACLs (acl-check)

```text
allowed_acls(region) =
  { policy.name |
    policy in acl/catalog.yaml, status=active,
    policy.vrf ∈ resolved_vrfs(region) }
```

Validation-scope device ACL references must be free of legacy names and must be
subset of `allowed_acls(region)`. In-scope hosts that failed trunk-check receive
`upstream_trunk_failed`.

### 4. Rendered bundles (render)

A host is rendered only when:

- it is in-scope (`legacy` or `partial`), and
- VLAN conformance passed (access), and
- trunk conformance passed, and
- if also in the validation scope, ACL conformance passed, and
- `interfaces/trunk/trunk_policy.yaml` access mode is `selective` and the
  running config has no `switchport trunk allowed vlan all`

`trunk_link_count` is the number of files under `trunks/links/` (not a
hard-coded constant).

`trunks/violations_seed.yaml` must use `schema_version:
apexora-trunk-violations-1` and an empty `violations` list (no residual
device mappings).

### 5. Deployment waves (wave-plan)

Wave readiness consumes the rendered host set. `missing_devices` includes:

- validation-scope hosts absent from wave phases, and
- in-scope validation-scope hosts absent from `rendered/`

Regional `*_batch` phases must only list hosts whose campus region matches.
Canary remains first; regional order remains `amer`, `emea`, `apac`.

### 6. Rollback manifests (rollback-audit)

Rollback indexing consumes `wave_readiness.json`. Hosts still listed in
`missing_devices` are reported missing. Bundle rows cover wave-derived
validation-scope hosts; durable forward/rollback paths and the active
`services/hooks/post-validate.sh <hostname>` command remain required.

### 7. Evidence (evidence)

Evidence is the final fan-in. It records live device observations plus a
`lineage` object summarizing upstream VLAN/VRF/ACL/render/wave/rollback
artifacts. Empty `legacy_sources_consulted` still requires
`consult_legacy_when_present: false`.

## Authority checkpoints

The authority checks are cumulative. `config_authoritative_m1` requires
authoritative assembly precedence, multi-source VLAN resolution without drift,
per-device access VLAN assignments, and canonical WAN-edge VRF bindings.
`config_authoritative_m2` includes M1 and adds selective trunk authority.
`config_authoritative_m3` includes M2 and adds ACL (VRF-derived), wave (render-
derived), and rollback (wave-derived) authority. A later export cannot
compensate for a failed earlier authority check.

All seven stages must be run through `scripts/run-netsegctl.sh`. Generated
artifacts are observations of the declarative configuration; editing
`/app/output` directly does not establish authority.

The verification harness records pytest results with the `--ctrf` reporting
option. This reporting detail does not alter pipeline behavior or authority.
