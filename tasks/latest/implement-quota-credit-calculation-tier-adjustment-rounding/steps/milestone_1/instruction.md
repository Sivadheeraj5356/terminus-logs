Implement production config loading and eligibility filtering for the coinsurance recovery batch under `/app`. The nightly run reads policy rows from `/app/data/coinsurance-policies.json`, loads rates from `/app/config/coinsurance-rules.properties` per `/app/docs/config-keys.md`, and writes `/app/output/coinsurance-report.json`. Staging copies such as `coinsurance-rules.override.properties` may remain on disk; production code must ignore them and read only the production properties file.

Eligibility

Include a policy only when status is approved case-insensitively, grossIncurred is greater than zero, and grossIncurred is greater than or equal to minimum.policy.amount read from production config. The minimum boundary is inclusive when otherwise eligible. Exclude inactive rows such as COI-002, zero-loss rows such as COI-004, sub-minimum rows such as COI-030, and below-minimum rows such as COI-006 and COI-008. Include COI-003 when status is APPROVED and COI-010 or COI-025 when grossIncurred equals the configured minimum exactly.

Report output for this step

Write `/app/output/coinsurance-report.json` with top-level keys `policies` and `summary` per `/app/docs/pricing-policy.md`. Each eligible policy row may keep computed money fields at zero until later milestones. Full row schema, `generatedAt`, sorting, Gson formatting, and summary rollups are completed in later steps.

Do not hardcode totals or edit `/app/data/coinsurance-policies.json` or production config files. Regenerate the report from `/app` with `mvn -q -B -o install -DskipTests` then `mvn -q -B -o -pl coinsurance-batch exec:java` and confirm eligibility.
