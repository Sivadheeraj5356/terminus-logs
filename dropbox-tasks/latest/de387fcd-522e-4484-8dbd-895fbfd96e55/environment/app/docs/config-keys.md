# Production Config Key Map

Maps business parameters to keys in `/app/config/coinsurance-rules.properties`.
Only the production keys documented here drive nightly batch totals. Other
entries in the same file are legacy staging aliases and must be ignored.

## Terminology

| Term | Meaning | Used for |
|------|---------|----------|
| **policyTier** | Label on the recovery row: `premium`, `plus`, or `basic` | `adjustment.tier.<policyTier>` lookup, impact-line tier adjustment basis, some rounding modes |

Report output must echo each recovery's `policyTier` string exactly as provided in
the input JSON. Config lookups normalize tier names for rate selection only.
| **deductibleAmount** | Fixed deductible applied after coinsurance rate | Reduces `coinsuranceBase` |
| **coinsuranceRate** | Fraction of gross incurred subject to coinsurance | Scales `coinsuranceBase` |
| **large loss line** | `coinsuranceBase >= coinsurance.threshold.large.loss` | Premium quota credit rate, premium holdback rate |
| **quota line** | `coinsuranceBase >= coinsurance.threshold.quota` | Quota credit eligibility, post-quota tier adjustment basis |

Quota-line detection always uses **coinsurance base**, never raw `grossIncurred`.
See `/app/docs/quota-addendum.md` for worked examples (including COI-009 and COI-016).

Large loss-line rates depend on **coinsurance base only**, not on `policyTier`.
A plus-tier or basic-tier recovery can still be a large loss line when the amount
crosses the threshold.

## Core keys

| Parameter | Production property key |
|-----------|-------------------------|
| Minimum recovery amount | `minimum.policy.amount` |
| Base recovery rate | `indemnity.share.rate` |
| Processing fee rate | `processing.fee.rate` |
| Standard quota credit rate | `quota.credit.rate` |
| Base premium holdback rate | `premium.holdback.rate` |
| Tier adjustment rates | `adjustment.tier.<policyTier>` (lowercase suffix) |
| Quota threshold | `coinsurance.threshold.quota` |

## Large loss parameters

Large loss pricing uses the `coinsurance.*` keys below.

| Parameter | Production property key |
|-----------|-------------------------|
| Large loss amount threshold | `coinsurance.threshold.large.loss` |
| Premium quota credit rate | `coinsurance.rate.quota.premium` |
| Premium holdback rate | `coinsurance.rate.holdback.premium` |

Apply premium quota credit rate when **both**:

- the recovery qualifies as a quota line (`coinsuranceBase >= coinsurance.threshold.quota`), and
- `coinsuranceBase >= coinsurance.threshold.large.loss`

Apply premium holdback rate when `coinsuranceBase >= coinsurance.threshold.large.loss`
alone — on any large loss line, regardless of `policyTier`.

## Loader requirements

Production batch loaders consume `/app/config/coinsurance-rules.properties` directly.
Ignore `coinsurance-rules.override.properties` and other staging-only property aliases.

Policy tier parameters are read from `adjustment.tier.<policyTier>` entries
using the lowercase suffix shown in the config file.
