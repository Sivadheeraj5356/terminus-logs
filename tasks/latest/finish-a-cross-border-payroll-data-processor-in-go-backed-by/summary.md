# Finish a cross-border payroll data processor in Go, backed by SQLite. A scaffold

- **UUID:** `6023158a-6fd3-4f0f-aec7-8b224e0004c7`
- **Slug:** `finish-a-cross-border-payroll-data-processor-in-go-backed-by`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Finish a cross-border payroll data processor in Go, backed by SQLite. A scaffold is waiting in /app: command wiring, SQLite plumbing, the statutory schedule tables, and the country-metadata loader are already there.

Nine pieces are stubbed out: employee/hours storage, progressive withholding, a currency-to-minor-unit mapping, a continent-to-region mapping, social contribution, a two-leg currency conversion, employee-country assignment, a country cost ranking, and a ceiling on total social spend per report run. Build with go build -o /app/crosspay .; offline, standard-library only.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
