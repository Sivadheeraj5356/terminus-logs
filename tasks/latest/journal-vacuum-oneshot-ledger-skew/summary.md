# Journal vacuum oneshot ledger skew

- **UUID:** `1036fcde-d250-446c-8149-ec417238e19e`
- **Slug:** `journal-vacuum-oneshot-ledger-skew`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Journal vacuum oneshot ledger skew After journal vacuum maintenance on this host, the shard-export oneshot unit (`verify-journal-export.service`) loses byte-ledger parity between `StandardOutput=journal` and `StandardOutput=file` launch settings. `journalctl -u verify-journal-export` shows truncated progress lines and collector-socket write abort when journald recycles mid-burst; the file-backed unit profile completes quietly on the same fixture packs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
