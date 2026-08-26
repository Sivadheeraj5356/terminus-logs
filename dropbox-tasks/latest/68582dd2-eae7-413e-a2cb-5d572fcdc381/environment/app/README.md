# Rootless deployment identity and ACL restore

Operations materialize tbundle backup bundles into a caller-supplied deployment root while enforcing a rootless identity boundary: mapped ownership and principal ACL metadata are recorded through user extended attributes rather than privileged `chown` or kernel ACL configuration. The layer runs without elevated privileges and preserves inode topology, extended attributes, and managed-path lifecycle rules.

## Layout

- `archives/` — bundled tbundle inputs
- `manifests/` — deployment manifests and preserve rules
- `config/idmap.toml` — subordinate UID/GID identity mapping for rootless deployment
- `docs/` — restore, manifest, log, and verification contracts
- `bin/restore-bundle` — operator entrypoint for deployment restore runs

## Operator workflow

1. Select a manifest under `/app/manifests`.
2. Run the restore workflow documented in `/app/docs/operations.md`.
3. Inspect mapped ownership and ACL principal records with `getfattr` and review `/output/restore-log.json`.

See `/app/docs/restore-contract.md` for phase ordering, cleanup rules, and preservation semantics.
