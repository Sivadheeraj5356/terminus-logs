# The May tap batches in /app/data need to be closed out. The current /app/reconci

- **UUID:** `b6180f8d-3fd8-4c68-81ce-56c25093807f`
- **Slug:** `the-may-tap-batches-in-app-data-need-to-be-closed-out-the-cu`
- **Category:** data-processing
- **Difficulty:** medium

## Summary

The May tap batches in /app/data need to be closed out. The current /app/reconcile.js is just a placeholder, so replace it with Node.js code that runs with `node /app/reconcile.js` using only the files and packages already present in the image.

Read the JSONL and CSV feeds, the late tap-correction feed, the temporary service-zone adjustment feed, the subsidy recovery feed, the settlement hold feed, the carry-forward credit feed, the credit reversal feed, the route-family minimum feed, the cap-exclusion feed, the account link feed, the account credit feed, /app/contracts/fare_policy.sqlite, and /app/docs/fare-policy.md. Do not change any raw input files or the policy database.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
