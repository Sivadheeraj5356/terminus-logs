# Audit report schema

`bastion-audit audit` writes JSON to the path given by `--report`.

| Field | Type | Meaning |
|-------|------|---------|
| `staging_root` | string | Absolute path to extracted staging tree |
| `tenant` | string | Tenant id used for registry overlay merge |
| `violations` | array | Drift records (empty when clean) |
| `clean` | boolean | `true` only when `violations` is empty |

Each violation object:

| Field | Type | Meaning |
|-------|------|---------|
| `path` | string | Relative path under staging root |
| `kind` | string | `ssh_key_mismatch`, `mode_mismatch`, `sshd_setting`, `sudoers_missing`, or `sudoers_unauthorized` |
| `expected` | string | Registry-authoritative value |
| `actual` | string | Observed staged value |

Violations must be sorted lexicographically by `path`, then `kind`.
