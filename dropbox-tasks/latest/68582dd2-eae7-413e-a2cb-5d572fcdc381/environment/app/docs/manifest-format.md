# Manifest format

Manifests are UTF-8 JSON files with `schema_version` 1.

## Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | integer | Must be `1`. |
| `archive` | string | Archive filename under the archives directory (`.tbundle`). |
| `restore_prefix` | string | Optional relative prefix under the restore root. Default `""`. |
| `preserve_paths` | array of strings | Relative paths under the restore root that must not be deleted by restore. |
| `entries` | array | Expected post-restore metadata per path. |

## Entry fields

Each `entries[]` item describes one restored path relative to `restore_prefix`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | yes | Normalized relative path using `/` separators. |
| `type` | string | yes | One of `file`, `dir`, `symlink`, `hardlink`. |
| `mode` | string | yes | Octal mode like `0644`. |
| `mapped_uid` | integer | yes | Ownership uid recorded in `user.restore.uid`. |
| `mapped_gid` | integer | yes | Ownership gid recorded in `user.restore.gid`. |
| `content_sha256` | string | for files | Lowercase hex digest of file bytes. |
| `symlink_target` | string | for symlinks | Stored symlink target after normalization (for example `../var/cache/token`). |
| `hardlink_group` | string | for hardlink groups | Shared identity token; the regular-file anchor and every `hardlink` member in a group share one inode (`shared_inode`), mapped ownership, payload metadata, and consistent `nlink`. Example token: `hl-shared`. |
| `xattr` | object | no | User xattrs excluding ownership and ACL keys (for example `user.svc.tier: primary`). These keys are included in the metadata log even for a symlink on a host that cannot physically attach user xattrs to symlink inodes. |
| `acl` | array of strings | no | POSIX ACL text lines stored in `user.restore.acl` JSON. |

Ownership and ACL are not applied with privileged syscalls. Restore records mapped uid/gid in `user.restore.uid` / `user.restore.gid` and ACL lines in `user.restore.acl`.


## Hardlink metadata inheritance

A `type=hardlink` archive member identifies its group through `hardlink_key` and normally omits source `uid` and `gid`. Its manifest row still contains the expected mapped ownership. Resolve that ownership from the regular-file archive member with the same `hardlink_key`; do not apply `fallback_uid`, `fallback_gid`, zero ownership, or values from an unrelated archive member. The same anchor supplies the group's payload identity and inherited archive metadata. Resolution is independent of archive and manifest record order.

Paths are normalized by resolving `.` and `..` against the restore prefix before metadata application.

## Ordering

Manifest `entries` may appear in any order. Verifiers compare normalized sets.
