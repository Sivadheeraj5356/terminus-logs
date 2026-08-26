# Debian and Ubuntu platform operators keep auditd-style rule stacks and

- **UUID:** `b6e42b2b-ebf0-4a16-90fb-b9a2599aa360`
- **Slug:** `debian-and-ubuntu-platform-operators-keep-auditd-style-rule`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Debian and Ubuntu platform operators keep auditd-style rule stacks and augenrules-style tier merges next to host audit policy. Host audit flavor is in /app/environment/etc/audit/auditd.conf, with rule-include flavor under /app/environment/etc/audit/rules.d/.

After ordinary rule reloads, a second reload cycle, or a syscall-class revoke, a bundled local readiness check can still report convergence while regenerated lineage under /app/output shows missing syscall classes, conflicting generation markers, or dropped rows that were previously accepted in the enforced view. Bring the host audit rule-reload and lineage path under /app/environment into line so /app/bin/arctl reload --profile <name> and /app/bin/arctl inspect --profile <name> regenerate /app/output/rule_lineage.json through the normal operator pipeline.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
