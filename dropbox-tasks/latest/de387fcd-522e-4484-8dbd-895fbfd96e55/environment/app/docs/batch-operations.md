# Batch Operations

Production nightly batch reads `/app/data/coinsurance-policies.json`, loads
`/app/config/coinsurance-rules.properties`, and writes `/app/output/coinsurance-report.json`.

Staging override files and legacy loaders under `coinsurance-engine/legacy/` are not
used by the production batch entrypoint (`com.coinsurancerecovery.batch.Main`).
