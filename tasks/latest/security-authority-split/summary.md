# security_authority_split

- **UUID:** `68582dd2-eae7-413e-a2cb-5d572fcdc381`
- **Slug:** `security-authority-split`
- **Category:** security
- **Difficulty:** hard

## Summary

The rootless deployment identity and ACL authority layer under `/app` enforces mapped ownership records, principal ACL metadata, inode-linked deployment content, and managed-path lifecycle rules for tbundle restores without elevated privileges. Recent bundle upgrades exposed wrong mapped ownership, duplicated hardlink payloads, missing ACL principal records, and non-deterministic repeat-restore logs.

Repair the restore authority layer so archives from `/app/archives` reconstruct `/output/restore-root` and `/output/restore-log.json` per `/app/docs/restore-contract.md`, `/app/docs/manifest-format.md`, and `/app/docs/log-schema.md`. The layer must enforce the documented rootless identity boundary, subordinate UID/GID mapping, and POSIX/PAX restore contract rather than bypass verification with regenerated artifacts.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
