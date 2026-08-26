Implement indemnity share, pipeline order, and tier adjustment basis in the coinsurance-engine module. Keep config loading and eligibility from the prior step intact. Limit this pass to `IndemnityShareCalculator`, `CoinsuranceProcessor` pipeline order, and `TierAdjustmentEngine` tier adjustment basis. Do not change quota credit rate formulas, rounding schedule rules, premium holdback logic, or report generation yet.

Compute each row's `indemnityShare` as `coinsuranceBase × indemnity.share.rate` per `/app/docs/pricing-policy.md` in `IndemnityShareCalculator`. Use each row's `coinsuranceBase()` (not raw `grossIncurred` or `getLossAmount()`). COI-009 shows why: `grossIncurred` can meet the quota threshold while `coinsuranceBase` does not after deductible and rate.

Compute quota credit before tier adjustment in `CoinsuranceProcessor`. Leave quota credit calculation unchanged in this step; tier adjustment must subtract each row's existing `quotaCreditAmount`.

Quota-line and post-quota basis

A row is a quota line only when `coinsuranceBase >= coinsurance.threshold.quota`, not when raw `grossIncurred` meets the threshold. For plus or premium policy tiers on quota lines, tier adjustment basis is `indemnityShare - quotaCreditAmount`. Apply the tier rate to that post-quota basis, not to raw `grossIncurred` and not to full `indemnityShare` when quota credit is non-zero. Non-quota lines keep the default `indemnityShare` basis. Further quota credit formulas and rounding exceptions remain in `/app/docs/quota-addendum.md` for the next step.

After regenerating the report from `/app` with `mvn -q -B -o install -DskipTests` followed by `mvn -q -B -o -pl coinsurance-batch exec:java`, confirm quota-line policies such as COI-016 and COI-018 show tier adjustment amounts consistent with the quota credit already present on each row.
