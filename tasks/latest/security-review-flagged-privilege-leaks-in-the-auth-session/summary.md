# Security review flagged privilege leaks in the auth session authority model unde

- **UUID:** `41e66a22-b1ed-4eef-bfd9-45555130451e`
- **Slug:** `security-review-flagged-privilege-leaks-in-the-auth-session`
- **Category:** security
- **Difficulty:** hard

## Summary

Security review flagged privilege leaks in the auth session authority model under `/app/environment`. Prior session generations can stay admit-capable after rotation (including skipped-generation seal chains), idle soft-refresh can stretch absolute lifetime past the issued privilege window across a long refresh sequence, concurrent session occupancy can slip the principal RBAC budget under login surge, and terminal journals can omit integrity fields while stage reports look fine.

The authority model must satisfy `/app/environment/docs/verify_contract.md` for both `tight` and `loose`: dual-valid windows stay closed across the full rotation peak, `abs_deadline` stays issued-plus-lifetime under soft refresh, surge occupancy seats at the principal budget, and `/app/output/epoch.ledger` stays coherent across repeated matrix runs and corruption recovery (exactly 8 ledger rows). Acceptance is the terminal `/app/output/witness.json` from `/app/environment/tools/sf_verify/sf_verify --matrix all --profiles tight,loose --witness-out /app/output/witness.json` after a successful `/app/environment/scripts/build_all.sh`; `/app/output/stage` and `/app/output/logs` alone are not enough.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
