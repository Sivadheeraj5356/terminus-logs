# EmbedServe inventory layout

Database path: `/app/data/embedserve_inventory.db`

## meta

| key | meaning |
|-----|---------|
| `generation` | Inventory schema generation (`2025-07`) |
| `inventory_source` | Active catalog label (`embedserve-production`) |

## deployment_profiles

| column | type |
|--------|------|
| `profile_id` | TEXT PK |
| `name` | TEXT |
| `enabled` | INTEGER (0/1) |

## cargo_components

Sidecar crate rows bound to a profile.

| column | type |
|--------|------|
| `profile_id` | TEXT |
| `crate_name` | TEXT |
| `version` | TEXT |
| `component_role` | TEXT (`tokenizer`, `runtime`, …) |
| `enabled` | INTEGER (0/1) |
| `advisory_id` | TEXT nullable |
| `disabled_reason` | TEXT nullable |

Primary key: (`profile_id`, `crate_name`).

## inference_defaults

| column | type |
|--------|------|
| `profile_id` | TEXT |
| `setting_key` | TEXT |
| `current_value` | TEXT |
| `hardened_value` | TEXT |
| `applied` | INTEGER (0/1) |

Primary key: (`profile_id`, `setting_key`).

## advisory_evidence

| column | type |
|--------|------|
| `profile_id` | TEXT |
| `advisory_id` | TEXT |
| `crate_name` | TEXT |
| `severity` | TEXT — lowercase token from `{medium, high, low, critical, warning}` (see harden contract severity normalization) |
| `package_spec` | TEXT |
| `recorded_at` | TEXT (UTC ISO-8601 `…Z`) |
| `audit_run_id` | TEXT |

## harden_runs

| column | type |
|--------|------|
| `run_id` | TEXT PK |
| `profile_id` | TEXT |
| `ops_digest` | TEXT (16 hex) |
| `lock_digest` | TEXT (16 hex) |
| `advisory_count` | INTEGER |
| `completed_at` | TEXT (UTC ISO-8601 `…Z`) |

## Post-harden SQL invariants (embedserve-default)

- `opened_db_basename` for reports is always `embedserve_inventory.db`.
- Every sidecar crate with a matching advisory from the lockfile scan has `enabled = 0` and non-null `advisory_id`.
- Operative inference defaults from Section 11 have `applied = 1` and `current_value` equal to `hardened_value`.
- `advisory_evidence` contains one row per disabled advisory with matching `crate_name` and `advisory_id`.
- A new `harden_runs` row records digests and advisory count.
