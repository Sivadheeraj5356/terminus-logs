# # YourList SMS Service Operations Runbook

- **UUID:** `50a239c8-a85a-47a6-9ab7-c5b04b1890b6`
- **Slug:** `yourlist-sms-service-operations-runbook`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Build an **offline system-administration runbook package** for the YourList SMS microservice. Inputs are frozen production snapshots under `/app/input/` (PM2 process logs, nginx edge access log, environment file, Express mount sources, and sample request bodies).

Write all artifacts under `/app/output/`. Do not modify the host, call Telnyx, or send SMS.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
