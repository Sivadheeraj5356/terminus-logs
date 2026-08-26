# The FinchRender render-farm coordinator is being migrated to systemd. Under `/ap

- **UUID:** `537f2158-beb1-4c07-bfcf-a4abb2d4f8a5`
- **Slug:** `the-finchrender-render-farm-coordinator-is-being-migrated-to`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The FinchRender render-farm coordinator is being migrated to systemd. Under `/app/docs/` you will find an operations dossier, a migration requirements spec, and an architecture overview.

Under `/app/traces/` are strace and lsof captures from the coordinator's startup and steady-state operation. Under `/app/legacy/` are the original YAML and TOML configuration files.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
