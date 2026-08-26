# Dependency Integrity Gate — Output Contract

## CLI

`modgate --manifest <manifest.json> --out <dir>`

Success stdout must contain the exact sentinel `MODGATE_OK`.

Required artifacts under `<dir>`:

| file | kind |
| --- | --- |
| `integrity_report.json` | JSON array |
| `integrity_certificate.json` | JSON object |
| `repro_digest_export.json` | JSON object |

Every helper path named by the evaluating manifest must resolve to a compiled native ELF binary. Non-ELF replacements are non-conforming.

## Path resolution

Manifest path shape: `{batch_root}/data/manifest.json`.

`batch_root` is the parent of the directory containing the manifest. Relative manifest paths resolve against `batch_root`. Absolute paths are used as given.

## Primary evaluation posture

| field | primary value |
| --- | --- |
| module_batch_id | EDGE-GO-MOD-Q1 |
| snapshot_pack | JAN_2025 |
| policy_track | PRODUCTION |
| pin_count | 15 |
| toolchain_declared | 1.21.0 |

Authoritative policy, overlay bindings, helper interfaces, and digest formulas are named from the evaluating manifest and its referenced materials. This contract states observable shapes only.

## `integrity_report.json`

Array sorted ascending by `mod_id`. Exactly one object per lock pin.

| field | type |
| --- | --- |
| `mod_id` | string |
| `module_path` | string |
| `version` | string |
| `member` | string |
| `linkage` | string (`direct` \| `transitive`) |
| `retracted` | boolean |
| `checksum_ok` | boolean |
| `go_floor_ok` | boolean |
| `excluded` | boolean |
| `effective_violation` | boolean |
| `gate_action` | string (`block` \| `warn` \| `pass`) |
| `policy_basis` | string |
| `resolve_source` | string (`proxy_live` \| `snapshot`) |
| `block_reason` | string |
| `declared_hash` | string |
| `live_hash` | string |
| `refresh_retract` | boolean |
| `refresh_sum` | boolean |

`policy_basis` enum: `exclude_skip`, `waiver_digest`, `retract_block`, `retract_warn_transitive`, `checksum_block`, `toolchain_block`, `live_refresh`, `snapshot_carry`.

When `effective_violation` is false, `block_reason` is `""`. When true, `block_reason` is one of `retract_notice`, `checksum_mismatch`, `toolchain_floor`.

Worked row fragment (illustrative shape only; not a primary-batch answer):

```json
{
  "mod_id": "MOD-EX",
  "module_path": "example.com/mod",
  "version": "v1.2.3",
  "member": "edge-api",
  "linkage": "direct",
  "retracted": false,
  "checksum_ok": true,
  "go_floor_ok": true,
  "excluded": false,
  "effective_violation": false,
  "gate_action": "pass",
  "policy_basis": "snapshot_carry",
  "resolve_source": "snapshot",
  "block_reason": "",
  "declared_hash": "h1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=",
  "live_hash": "h1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=",
  "refresh_retract": false,
  "refresh_sum": false
}
```

## `integrity_certificate.json`

| field | type |
| --- | --- |
| `status` | string (`MODGATE_OK`) |
| `module_batch_id` | string |
| `policy_track` | string |
| `toolchain_declared` | string |
| `gate_status` | string (`block` \| `warn` \| `pass`) |
| `record_count` | integer |
| `live_refreshes` | integer |
| `waiver_hits` | integer |
| `stale_overrides` | integer |
| `retract_hits` | integer |
| `checksum_failures` | integer |
| `toolchain_blocks` | integer |
| `exclude_skips` | integer |
| `transitive_warns` | integer |
| `chain_digest` | string (64 lowercase hex) |
| `export_digest` | string (64 lowercase hex) |
| `member_rollups` | array |
| `resolutions` | array |

### `member_rollups[]` (sorted by `member`)

| field | type |
| --- | --- |
| `member` | string |
| `pin_count` | integer |
| `gate_status` | string (`block` \| `warn` \| `pass`) |

### `resolutions[]` (same order as report)

| field | type |
| --- | --- |
| `mod_id` | string |
| `policy_basis` | string |
| `resolve_source` | string |
| `gate_action` | string |

`gate_status` is `block` if any row is `block`, else `warn` if any row is `warn`, else `pass`.

## `repro_digest_export.json`

| field | type |
| --- | --- |
| `module_batch_id` | string |
| `export_digest` | string (64 lowercase hex) |
| `pin_digests` | array sorted by `mod_id` |

### `pin_digests[]`

| field | type |
| --- | --- |
| `mod_id` | string |
| `row_digest` | string (64 lowercase hex) |

## Cross-artifact invariants

INV1: `record_count` equals `integrity_report.json` length.

INV2: every lock `mod_id` appears once in the report, once in `resolutions`, and once in `pin_digests`.

INV3: each `resolutions` entry mirrors the matching report row for `policy_basis`, `resolve_source`, and `gate_action`.

INV4: `live_refreshes` equals the conflict-roster size for the evaluating batch.

INV5: `stale_overrides` matches the evaluating batch’s stale-delta rule from the signed annex.

INV6: certificate `export_digest` equals `repro_digest_export.json` `export_digest`.

INV7: every report `member` appears once in `member_rollups`, and each rollup `pin_count` equals the number of report rows for that member.

## Protected paths

Do not modify bundled corpus files, lock fixtures, snapshots, conflict report, overlays, manifest, or this contract.
