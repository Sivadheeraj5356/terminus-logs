# Finance rejected /app/bin/commitment-chargeback. Totals discounts pool shares an

- **UUID:** `7abf1f09-a031-4813-87a4-539f49cce12a`
- **Slug:** `finance-rejected-app-bin-commitment-chargeback-totals-discou`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Finance rejected /app/bin/commitment-chargeback. Totals discounts pool shares and report digest disagree and reruns are not byte identical.

Edit only commitment.go ratecard.go intake.go and main.go under /app/carrydown_engine. Leave all other carrydown_engine files and leave /app/pledge_inputs and /app/billing_contracts byte identical write protected.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
