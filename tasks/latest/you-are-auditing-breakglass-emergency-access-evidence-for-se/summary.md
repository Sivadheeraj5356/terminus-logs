# You are auditing breakglass emergency-access evidence for security-control viola

- **UUID:** `c188016a-8869-47b5-a7d2-a873e10a26c6`
- **Slug:** `you-are-auditing-breakglass-emergency-access-evidence-for-se`
- **Category:** security
- **Difficulty:** hard

## Summary

You are auditing breakglass emergency-access evidence for security-control violations. The records in `/app/input_data` cover principals, protected resources, incident tickets, approvers, privileged access requests, approval decisions, session events, and revocations from a production emergency-access system.

Produce the offline security ledger package at `/app/output_data/breakglass_ledger.json`, creating `/app/output_data` if needed. The output JSON has only `ledger_entries` and `severity_index`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
