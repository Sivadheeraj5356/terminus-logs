# # Kafka Consumer Backlog Crisis

- **UUID:** `001ea154-61a1-41ee-a51a-44e8f22786f8`
- **Slug:** `kafka-consumer-backlog-crisis`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Order-ingest is tens of thousands of records behind. CPU and memory stay flat, so scale-out is off the table for this shift.

The offline recovery bench under `/app/environment` loads cluster metadata, runs workload scenarios, and writes `/app/ingest_recovery_report.json` with `scenarios` and a `recovery_digest` (64-character lowercase hexadecimal). Field meanings, numeric health rules, and how to regenerate the report live in `/app/environment/data/report_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
