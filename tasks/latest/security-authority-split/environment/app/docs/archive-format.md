# Archive format

Bundles use the `tbundle-1` JSON format stored as `.tbundle` files under `/app/archives`.

## Top-level fields

| Field | Description |
|-------|-------------|
| `format` | Must be `tbundle-1`. |
| `entries` | Ordered list of archive members. |

## Entry fields

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Relative member path; may include `.` segments before normalization. |
| `type` | string | `file`, `dir`, `symlink`, or `hardlink`. |
| `mode` | string | Octal mode for materialized members. |
| `uid`, `gid` | integer | Source ownership recorded in the archive. |
| `content_b64` | string | Base64 payload for regular files. |
| `symlink_target` | string | Target for symlink members. |
| `hardlink_key` | string | Shared identity token for hardlink members. |
| `xattr` | object | User extended attributes to restore. |
| `acl` | array | POSIX ACL text lines. |

The reader in `/app/src/archive/reader.py` loads archives without applying id-map rules.
