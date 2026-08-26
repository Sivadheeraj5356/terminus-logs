Implement quota credit calculation, tier adjustment rounding, and premium holdback logic in the coinsurance-engine module. Keep indemnity share, pipeline order, and tier adjustment basis from the prior step intact.

Compute quota credit on indemnity share using each row's `coinsuranceBase` for rate selection per `/app/docs/config-keys.md` and `/app/docs/quota-addendum.md`, not raw `grossIncurred`. Use `quota.credit.rate` unless both quota line and large loss line apply, then use `coinsurance.rate.quota.premium`. Premium holdback rates apply when `coinsuranceBase >= coinsurance.threshold.large.loss`, not from policy tier alone.

Rounding exceptions for this step

Apply these HALF_DOWN exceptions from `/app/docs/rounding-schedule.md`; all other money fields stay HALF_UP unless noted in the addenda:

- `quotaCreditAmount`: HALF_DOWN when premium policy tier on a quota line
- `tierAdjustmentAmount`: HALF_DOWN when plus tier on a quota line; HALF_DOWN when premium tier on a premium loss line
- `premiumHoldbackAmount`: HALF_DOWN on quota lines

Premium holdback taxable base is `indemnityShare - tierAdjustmentAmount - quotaCreditAmount + processingFeeAmount` per `/app/docs/premium-holdback-addendum.md`. Basic tier policies exactly at minimum.policy.amount receive zero premium holdback.

After updating coinsurance-engine logic, regenerate the report from `/app` with `mvn -q -B -o install -DskipTests` followed by `mvn -q -B -o -pl coinsurance-batch exec:java` and confirm rounding-sensitive policies such as COI-028 and COI-031 match the documented schedule.
