# Night cutover left the PAM auth fabric under /app disagreeing with itself. /app/

- **UUID:** `e0bb6423-aadd-4c9b-8b66-7b77a721ebeb`
- **Slug:** `night-cutover-left-the-pam-auth-fabric-under-app-disagreeing`
- **Category:** security
- **Difficulty:** hard

## Summary

Night cutover left the PAM auth fabric under /app disagreeing with itself. /app/scripts/stack_probe.sh prints CLEAN, but replaying the pack through /app/tools/auth_tape_replay (which drives /app/bin/pam_audit) still produces wrong lockout totals, wrong stack bindings on mixed-service conversations, expired principals reading active, and non-counted module noise inflating faillock.

Signed desk tip packets under /app/data/corp are the authoritative polarity source. Cutover left /app/ctl planes, /app/rt defaults, and durable tallies under /app/var/tally out of sync with that tip; /app/docs/operations.md states durable ledger hygiene against the signed carry tip.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
