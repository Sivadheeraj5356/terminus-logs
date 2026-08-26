# Harden report JSON contract

Written to `/app/out/harden_report.json` by the hardening CLI.

## Top-level fields

| Field | Type | Meaning |
|-------|------|---------|
| `api_version` | string | `2025-07` |
| `profile` | string | CLI profile name |
| `opened_db_basename` | string | Basename of inventory SQLite opened |
| `ops_section` | integer | Operative amendment section number (`11`) |
| `ops_digest` | string | First 16 lowercase hex chars of SHA-256 over UTF-8 Section 11 body (from `## Section 11` through the byte before the next top-level `##`) |
| `lock_digest` | string | First 16 lowercase hex chars of SHA-256 over tokenizer `Cargo.lock` bytes |
| `disabled_components` | array | Sorted by `crate_name` |
| `inference_defaults_applied` | array | Sorted by `setting_key` |
| `advisory_evidence_count` | integer | Rows inserted into `advisory_evidence` |
| `sql_evidence` | object | Inventory mutation summary |

## disabled_components row

| Field | Type |
|-------|------|
| `crate_name` | string |
| `version` | string |
| `advisory_id` | string |

## inference_defaults_applied row

| Field | Type |
|-------|------|
| `setting_key` | string |
| `value` | string |

Only operative keys from Section 11 appear: `model_sandbox_enabled`, `allow_local_weight_files`, `mmap_model_weights`, `tokenizer_remote_code`, `tokenizer_trust_remote_code`.

## sql_evidence

| Field | Type |
|-------|------|
| `inventory_path` | string | Absolute inventory path (`/app/data/embedserve_inventory.db`) |
| `components_disabled` | integer | Count of `cargo_components` rows set to `enabled = 0` with advisory |
| `defaults_changed` | integer | Count of `inference_defaults` rows with `applied = 1` |

## Advisory scan

Run offline from the tokenizer sidecar directory:

```text
cd /app/environment/sidecar/tokenizer
cargo audit --json --db /app/environment/fixtures/rustsec-advisory-db --file Cargo.lock -n
```

Only vulnerabilities whose `package.name` matches a `cargo_components` row with `component_role = tokenizer` for the active profile are disabled.

### Severity normalization

Persist `advisory_evidence.severity` as a lowercase token from this closed set:

`medium`, `high`, `low`, `critical`, `warning`

Read severity from the cargo-audit JSON hit in order: top-level `severity` on the vulnerability item, then `advisory.severity`. If neither is present or the value is empty, store `medium`. Do not invent other labels (for example CVSS strings or title case).

## Operative operations policy

Section 11 of `/app/docs/embedserve-operations-bundle.md` supersedes Section 4 defaults. Pending amendment rows in Section 11 are not operative. Ratified row **A-2025-07** controls:

| setting_key | hardened value |
|-------------|----------------|
| `model_sandbox_enabled` | `true` |
| `allow_local_weight_files` | `false` |
| `mmap_model_weights` | `false` |
| `tokenizer_remote_code` | `false` |
| `tokenizer_trust_remote_code` | `false` |

`tokenizer_max_vocab` is informational (`50257`) and is not persisted to `inference_defaults`.
