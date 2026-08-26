# Independent holdout replays for the rutile privilege analyzer disagree with the

- **UUID:** `023c4ea9-6a0a-477c-875e-b51ae5aa1621`
- **Slug:** `independent-holdout-replays-for-the-rutile-privilege-analyze`
- **Category:** security
- **Difficulty:** medium

## Summary

Independent holdout replays for the rutile privilege analyzer disagree with the platform analysis contract: exported edge inventories, escalation chains, and report attestations do not reconcile across the bundled holdout profile set. Restore full contract compliance for every holdout profile.

Regenerated reports written to `/app/output/escalation_report.json` must include `profile`, `identity_count`, `edges`, `chains`, and `report_digest_hex` and satisfy the platform output schema, channel semantics, ordering invariants, and digest attestation rules. Contract-conformant exports depend on a corrected analyzer implementation; static or hand-authored artifacts alone are insufficient.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
