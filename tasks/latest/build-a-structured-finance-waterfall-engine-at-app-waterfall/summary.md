# Build a structured finance waterfall engine at /app/waterfall.go. Reads /app/inp

- **UUID:** `e006dba1-ee31-4298-ab68-00735913a6b5`
- **Slug:** `build-a-structured-finance-waterfall-engine-at-app-waterfall`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Build a structured finance waterfall engine at /app/waterfall.go. Reads /app/input/collections.json, writes /app/output/waterfall.json.

Input has tranches (id, class A/B/C/residual, balance, coupon_rate) and periods (period, collections, defaults, prepayments, senior_fee, servicer_fee). Original pool balance = sum of starting tranche balances.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
