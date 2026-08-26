# Build a risk model that outputs, for each open repair ticket, a calibrated proba

- **UUID:** `2b5592e0-14a5-4aa7-998b-2e19833eb246`
- **Slug:** `build-a-risk-model-that-outputs-for-each-open-repair-ticket`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Build a risk model that outputs, for each open repair ticket, a calibrated probability it needs a repeat truck-roll within thirty days and whether to assign a senior technician now. You inherit a pipeline at /app/analysis.R whose validation looks strong but does not generalize to the open tickets; diagnose why and make them trustworthy.

The data is /app/data/service_ledger.csv; schema in /app/contracts/schema.md, artifacts in /app/contracts/output_contract.md. Each row is one ticket.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
