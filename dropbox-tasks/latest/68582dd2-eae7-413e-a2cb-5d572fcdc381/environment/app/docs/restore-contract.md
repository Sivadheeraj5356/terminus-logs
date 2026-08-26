# Restore contract

The restore utility runs without elevated privileges. It reads tbundle archives and manifests, applies id-map rules from `/app/config/idmap.toml`, and writes restored content under the configured output root.

## CLI

```
restore-bundle \
  --archives-dir PATH \
  --manifest PATH \
  --output PATH \
  --idmap PATH \
  --log PATH
```

`python3 -m restore.restore_main` accepts the same flags and runs with `PYTHONPATH=/app/src:/app`.

## Restore phases

1. **Plan** — Load manifest and archive. Normalize all paths. Compute the managed path set as every manifest entry path plus every archive entry path under the manifest `restore_prefix`.
2. **Cleanup** — Delete files and symlinks under the output root that are in the managed set from a prior run but not in the new managed set. Never delete paths listed in `preserve_paths`. Directories are removed only when empty after file cleanup. After switching manifests, paths from the prior managed set must not remain on disk (`exists()` is false).
3. **Materialize** — Create every archive member type: directories, regular files, symlinks, and hardlink paths. Hardlink members are created after the regular-file anchor for their `hardlink_key` exists. Every materialized archive member, including directories and hardlink paths, is included in `entries_restored`.
4. **Metadata** — For each manifest path in lexicographic order: apply mode where the platform permits it, record mapped ownership xattrs, copy declared user xattrs where physically supported, then store ACL lines. Metadata must not be applied before the path exists. The metadata log records the complete declared key set even when the filesystem cannot attach a key to that entry type.
5. **Log** — Write `/output/restore-log.json` per the log schema.

## Id-map rules

Read `/app/config/idmap.toml`:

- `defaults.subuid_base` / `subgid_base` — added to non-overridden archive uid/gid values.
- `defaults.fallback_uid` / `fallback_gid` — used when no rule matches.
- `override` rows match exact `(source_uid, source_gid)` pairs and replace the mapped values.

Mapped ownership is stored only in `user.restore.uid` and `user.restore.gid` xattrs.

## Hardlinks

Archive hardlink members share a `hardlink_key`. Exactly one regular-file member in the group is the ownership and payload anchor. A `type=hardlink` archive entry may omit `uid`, `gid`, payload, user xattrs, and ACLs; omitted metadata is inherited from that regular-file anchor rather than mapped from fallback or zero values. Restore must create additional paths with `os.link` to the first materialized member so inode, mapped ownership, content, metadata, and link count agree across the group. Copying file bytes is incorrect. Manifest `hardlink_group` values identify members that must share one inode; grouped paths must report `shared_inode` as true with `nlink` equal to the number of paths in the group. Archive and manifest entry order must not change anchor resolution.

## Extended attributes and symlinks

Archive or manifest `xattr` values are part of the declared metadata contract and must be applied to supported restored objects in deterministic key order. Ownership keys (`user.restore.uid`, `user.restore.gid`) and ACL storage (`user.restore.acl` when ACL lines are present) are recorded in addition to declared user keys. On platforms where user xattrs cannot be attached to a symlink itself, restore must not follow the symlink and alter its target merely to apply them. The corresponding metadata log record must still list every declared and synthesized xattr key for that symlink, because `xattr_keys` describes the metadata contract evaluated for the path, not only keys physically written by the host filesystem.

## Idempotency

Running restore twice with the same inputs must produce identical filesystem metadata and byte-identical log output.

## Preservation

Files listed in `preserve_paths` survive cleanup even when absent from the archive. Restore must not overwrite an existing preserved file.
