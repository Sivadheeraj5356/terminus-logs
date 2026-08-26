# Implement quota credit calculation, tier adjustment rounding, and premium holdba

- **UUID:** `de387fcd-522e-4484-8dbd-895fbfd96e55`
- **Slug:** `implement-quota-credit-calculation-tier-adjustment-rounding`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Implement quota credit calculation, tier adjustment rounding, and premium holdback logic in the coinsurance-engine module. Keep indemnity share, pipeline order, and tier adjustment basis from the prior step intact.

Compute quota credit on indemnity share using each row's `coinsuranceBase` for rate selection per `/app/docs/config-keys.md` and `/app/docs/quota-addendum.md`, not raw `grossIncurred`. Use `quota.credit.rate` unless both quota line and large loss line apply, then use `coinsurance.rate.quota.premium`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
