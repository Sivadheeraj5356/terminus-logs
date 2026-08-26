# Restore log schema

`schema_version` is always `1`.

```json
{
  "schema_version": 1,
  "manifest": "simple-svc.json",
  "archive": "simple-svc.tbundle",
  "restore_root": "/output/restore-root",
  "status": "ok",
  "entries_restored": ["etc", "etc/config.json", "service", "service/bin", "service/bin/run"],
  "metadata_applied": [
    {
      "path": "etc/config.json",
      "mapped_uid": 101001,
      "mapped_gid": 101001,
      "xattr_keys": ["user.restore.acl", "user.restore.gid", "user.restore.uid", "user.svc.tier"],
      "acl": ["user::rw-", "group::r--", "other::r--"]
    }
  ]
}
```

## Fields

| Field | Description |
|-------|-------------|
| `entries_restored` | Sorted, duplicate-free list of every normalized archive member path materialized by the restore, including `file`, `dir`, `symlink`, and `hardlink` entries. Implicit parent directories created only to reach an archive member are excluded unless they are themselves archive entries. |
| `metadata_applied` | Sorted by `path`. Each record lists mapped ownership, sorted `xattr_keys`, and ACL lines in archive order. |

Log output must be deterministic: sorted keys, UTF-8, trailing newline, no absolute temporary paths.


## Metadata key reporting

`xattr_keys` is the sorted, duplicate-free set of metadata keys declared for that restored path: all user keys from its manifest metadata, `user.restore.uid`, `user.restore.gid`, and `user.restore.acl` when ACL lines are present. It describes the metadata contract evaluated for the path. Therefore the keys remain present in the log for symlinks even when the host filesystem does not permit writing user xattrs to the symlink inode. Restore must not follow the symlink and apply those keys to its target.

For a hardlink member, `mapped_uid` and `mapped_gid` are inherited from the regular-file archive anchor sharing its `hardlink_key`; they are not derived from fallback ownership merely because the hardlink record omits source ownership fields.
