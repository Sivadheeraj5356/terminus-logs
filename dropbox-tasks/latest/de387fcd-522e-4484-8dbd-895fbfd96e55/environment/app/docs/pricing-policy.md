# Coinsurance Recovery Pricing Policy

Numeric parameters live in `/app/config/coinsurance-rules.properties`. Production
batch jobs must ignore `coinsurance-rules.override.properties` and other staging
aliases.

## Report structure

Write `/app/output/coinsurance-report.json` with exactly three top-level keys:
`generatedAt`, `policies`, and `summary`. Do not rename these keys.

The `policies` array holds one object per included row. The `summary` object
holds rollups listed in the Summary block below.

## Eligibility

A recovery is included when **all** of the following hold:

- `status` matches approved **case-insensitively**. Values such as `"approved"`,
  `"Approved"`, and `"APPROVED"` all qualify; `"pending"` does not.
- `grossIncurred` is greater than zero
- loss amount is greater than or equal to `minimum.policy.amount`

## Base recovery

`coinsuranceBase = max(0, grossIncurred × coinsuranceRate - deductibleAmount)`, rounded half-up to two decimals.

`indemnityShare = coinsuranceBase × indemnity.share.rate`, rounded half-up to two decimals.

## Processing fee

`processingFeeAmount = coinsuranceBase × processing.fee.rate`, rounded half-up to two
decimals. The fee increases the premium holdback base.

## Tier adjustment

Read `adjustment.tier.<policyTier>`. Default:
`tierAdjustmentAmount = indemnityShare × tierRate`, rounded half-up.

Quota-line tier adjustment basis and rounding exceptions are in
`/app/docs/quota-addendum.md`, `/app/docs/config-keys.md`, and
`/app/docs/rounding-schedule.md`.

## Quota credit adjustment

When `coinsuranceBase >= coinsurance.threshold.quota`, apply a quota credit using
config rates. Default quota credit rounding is half-up.

The credit amount is computed on **indemnity share**, not raw gross incurred:

`quotaCreditAmount = indemnityShare × rate`

Premium quota rates and tier-specific rounding are defined in the addenda above.

## Premium holdback

See `/app/docs/premium-holdback-addendum.md` and `/app/docs/config-keys.md`.

## Net recovery

`netRecovery = indemnityShare - tierAdjustmentAmount - quotaCreditAmount + processingFeeAmount - premiumHoldbackAmount`

## Sorting

Sort included policies by `netRecovery` descending. Break ties using `id` ascending.

## Summary block

- `policyCount`, `totalIndemnityShare`, `totalProcessingFee`, `totalTierAdjustment`,
  `totalQuotaCredit`, `totalPremiumHoldback`, `totalRecovery`

## Report metadata

Include `generatedAt` as UTC ISO-8601 ending with `Z`.

Each recovery row: `id`, `insurer`, `grossIncurred`, `deductibleAmount`, `coinsuranceRate`, `policyTier`, `indemnityShare`,
`processingFeeAmount`, `adjustmentRate`, `tierAdjustmentAmount`, `quotaCreditAmount`,
`premiumHoldbackAmount`, `netRecovery`.

## Pass-through row fields

Copy `id`, `insurer`, `grossIncurred`, `deductibleAmount`, `coinsuranceRate`, and `policyTier` from the input recovery
unchanged. Preserve the original string casing of `policyTier` exactly as it
appears in `/app/data/coinsurance-policies.json` (for example `PREMIUM` must stay `PREMIUM`).

Rate lookups use case-insensitive tier matching against config keys; that
normalization applies to calculations only, not to the serialized report row.

## JSON money serialization

Money fields must be **JSON number literals** with exactly two decimal places in
the serialized text — not JSON strings. For example `"grossIncurred": 1500.00` is
correct; `"grossIncurred": "1500.00"` is not.

Report `adjustmentRate` and `coinsuranceRate` the same way (for example `0.00` for a zero adjustment rate, and `0.90` instead of `0.9` for a pass-through coinsurance rate).

Use Gson pretty-printing with a space after each colon (for example
`"grossIncurred": 1500.00`, not `"grossIncurred":1500.00`).
