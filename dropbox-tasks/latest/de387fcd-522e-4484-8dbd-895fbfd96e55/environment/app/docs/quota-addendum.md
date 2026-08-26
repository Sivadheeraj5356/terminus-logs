# Quota Credit Addendum

When `coinsuranceBase >= coinsurance.threshold.quota`:

1. Compute quota credit on **indemnityShare** (not grossIncurred).
2. Use `quota.credit.rate` unless both quota line and large loss line apply,
   then use `coinsurance.rate.quota.premium`.
3. Round HALF_DOWN for premium policy tier; otherwise HALF_UP.

`coinsuranceBase = max(0, grossIncurred × coinsuranceRate - deductibleAmount)`, rounded half-up to two decimals.

## Quota-line classification

A row is a **quota line** only when its **coinsurance base** meets the threshold:

`coinsuranceBase >= coinsurance.threshold.quota`

Do **not** classify quota lines using raw `grossIncurred`, `getLossAmount()`, or staging keys such as `loss.threshold.staging`.

**Example (COI-009):** `grossIncurred = 10000.00` with `deductibleAmount = 2500.00` and `coinsuranceRate = 0.75` yields `coinsuranceBase = 5000.00`, so the row is **not** a quota line even though gross incurred equals the quota threshold.

**Example (COI-016):** `grossIncurred = 25500.00`, `deductibleAmount = 0.00`, `coinsuranceRate = 1.00` yields `coinsuranceBase = 25500.00`, so the row **is** a quota line. For plus or premium tiers, tier adjustment uses the post-quota basis (`indemnityShare − quotaCreditAmount`), not full `indemnityShare` when quota credit is non-zero.

## Post-quota tier adjustment basis

Compute quota credit before tier adjustment on every row.

For premium or plus policy tiers on quota lines, tier adjustment basis is
`indemnityShare - quotaCreditAmount` (not raw grossIncurred and not full
`indemnityShare` when quota credit is non-zero). Non-quota lines keep the
default `indemnityShare` basis.
