# We've got a SIEM custody attestation stack under /app that is supposed to crypto

- **UUID:** `2521620b-0f89-41c8-99c7-090fe2302926`
- **Slug:** `we-ve-got-a-siem-custody-attestation-stack-under-app-that-is`
- **Category:** security
- **Difficulty:** medium

## Summary

We've got a SIEM custody attestation stack under /app that is supposed to cryptographically authenticate incident evidence and reject forged or skewed timelines against the signed anti-tamper budgets. In practice operators are seeing witness-MAC seal drift, custody-head breaks across pack order, and rotate-policy epoch mismatches, so hostile packs can still look intact when they are not.

Can you restore anti-tamper conformance in /app/chronctl and then emit /app/output/timeline_report.json from /app/data/scenarios.json? The report shape follows /app/docs/report_layout.json and /app/pkg/api/types.go: top-level schema_version, a scenarios array in pack order, and per-row name, finish, active_session_epoch, events_replayed, chain_intact, order_drift_count, contradiction_count, witness_ok_count, and timeline_head_hex.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
