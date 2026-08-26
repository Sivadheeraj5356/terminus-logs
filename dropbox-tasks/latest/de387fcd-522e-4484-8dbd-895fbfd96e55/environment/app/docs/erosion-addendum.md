# Erosion Credit Addendum

When `coinsuranceBase >= coinsurance.threshold.quota`:

1. Compute quota credit on **indemnityShare** (not grossIncurred).
2. Use `quota.credit.rate` unless both quota line and large loss line apply,
   then use `coinsurance.rate.quota.premium`.
3. Round HALF_DOWN for premium policy tier; otherwise HALF_UP.

`coinsuranceBase = max(0, min(grossIncurred, aggregateLimit - deductibleAmount))`, rounded half-up to two decimals.

## Post-erosion tier adjustment basis

For premium or plus policy tiers on quota lines, tier adjustment basis is
`indemnityShare - quotaCreditAmount` (not raw grossIncurred).
