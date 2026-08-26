# Operations

## Restore a manifest

```bash
/app/bin/restore-bundle \
  --archives-dir /app/archives \
  --manifest /app/manifests/simple-svc.json \
  --output /output/restore-root \
  --idmap /app/config/idmap.toml \
  --log /output/restore-log.json
```

## Inspect restored ownership

Mapped ownership is stored in user xattrs:

```bash
getfattr -n user.restore.uid /output/restore-root/simple/etc/config.json
getfattr -n user.restore.gid /output/restore-root/simple/etc/config.json
```

## Repeat restore

Re-running the same command must converge to the same tree and log bytes. Switching manifests removes paths managed only by the prior manifest, such as `simple/etc/config.json` after restoring `meta-svc.json`.

## Preservation markers

Manifest `preserve_paths` entries such as `simple/.operator-marker` and `meta/.operator-marker` must survive restore even if absent from archives.
