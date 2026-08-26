# This is a security finding, not a routine bug report: chainaudit's tamper-eviden

- **UUID:** `d06b4e3f-699c-45e7-953c-87a677cff59b`
- **Slug:** `this-is-a-security-finding-not-a-routine-bug-report-chainaud`
- **Category:** security
- **Difficulty:** hard

## Summary

This is a security finding, not a routine bug report: chainaudit's tamper-evidence guarantee for the compliance event log has a detection bypass. Since last month's storage migration, verify can't reliably tell real tampering from harmless encoding differences — a checkpoint genuinely altered during the incident currently verifies as clean, while unrelated streams get flagged as corrupt, exactly the noise that trains people to ignore alerts that matter.

Until this is closed, the tamper-evidence property this system exists to provide does not actually hold. Two things, in order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
