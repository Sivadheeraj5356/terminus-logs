# Process the securities lending fee ledger input data with /app/securities_lendin

- **UUID:** `5919ecf1-9cc7-4365-b8af-84f8f144df23`
- **Slug:** `process-the-securities-lending-fee-ledger-input-data-with-ap`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Process the securities lending fee ledger input data with /app/securities_lending_fee.go, compiled to /app/securities_lending_fee. It should read /app/input/lending_batches.csv, /app/input/borrowers.csv, and /app/input/fee_accruals.jsonl, then write /app/output/securities_lending_fee_report.json; if INPUT_DIR or OUTPUT_DIR is set, use those directories instead.

lending_batches.csv has batch_id,cutoff_at, borrowers.csv has borrower_id,lending_desk,active_limit, and fee_accruals.jsonl has fee_id, lending_batch_id, borrower_id, accrued_at, loan_sequence, fee_type, fee_cents, and rebates_fee_id. Trim strings, treat missing strings as empty and missing numbers as zero, parse timestamps as RFC3339 instants, and emit JSON numbers as numbers.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
