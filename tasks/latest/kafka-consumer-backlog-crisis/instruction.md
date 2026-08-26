# Kafka Consumer Backlog Crisis

Order-ingest is tens of thousands of records behind. CPU and memory stay
flat, so scale-out is off the table for this shift.

The offline recovery bench under `/app/environment` loads cluster metadata,
runs workload scenarios, and writes `/app/ingest_recovery_report.json` with
`scenarios` and a `recovery_digest` (64-character lowercase hexadecimal).
Field meanings, numeric health rules, and how to regenerate the report live in
`/app/environment/data/report_contract.md`. Workload shapes and `tick_budget`
are in `/app/environment/data/workloads.json`. Operator notes elsewhere under
`/app/environment` may disagree with each other or with the cluster file.

Repair the Go sources so every scenario in the regenerated report meets the
contract. Static hand-written reports are insufficient: the verifier deletes
the report and rebuilds it from source. Leave `/app/environment/tools/`
unchanged.
