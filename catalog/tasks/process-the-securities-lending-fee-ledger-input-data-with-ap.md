# Process the securities lending fee ledger input data with /app/securities_lendin

Submission: `5919ecf1-9cc7-4365-b8af-84f8f144df23`  
Slug: `process-the-securities-lending-fee-ledger-input-data-with-ap`  
Latest archive: `5919ecf1-9cc7-4365-b8af-84f8f144df23_submission_2026-07-11T10_46_05.776Z.zip`  
Revisions in Dropbox: 9

## Task summary

Process the securities lending fee ledger input data with /app/securities_lending_fee.go, compiled to /app/securities_lending_fee. It should read /app/input/lending_batches.csv, /app/input/borrowers.csv, and /app/input/fee_accruals.jsonl, then write /app/output/securities_lending_fee_report.json; if INPUT_DIR or OUTPUT_DIR is set, use those directories instead. lending_batches.csv has batch_id,cutoff_at, borrowers.csv has borrower_id,lending_desk,active_limit, and fee_accruals.jsonl has fee_id, lending_batch_id, borrower_id, accrued_at, loan_sequence, fee_type, fee_cents, and rebates_fee_id. Trim strings, treat missing strings as empty and missing numbers as zero, parse timestamps as RFC3339 instants, and emit JSON numbers as numbers. Replay the load rows in a stable order: invalid timestamps first in input order, then valid rows by event time, sequence, and id. After every row, mark its id as seen even when rejected; a later same id is duplicate unless its own timestamp is invalid. Use the first matching rejection reason in this order: invalid timestamp, duplicate id, unknown batch, after watermark, unknown entity, invalid kind, negative amount, entity cap exceeded, state conflict. Rejected rows never change current records, accepted ids, entity totals, batch net amounts, reversal state, or trace rows; rejected_events in batch_audit counts only rejected rows with a known batch. A row is after watermark when its event time is later than its batch cutoff. Valid kinds are accrual and rebate. accrual rows need fee_cents at least zero and are rejected as entity cap exceeded...

Required artifacts include: `/app/securities_lending_fee.go`, `/app/securities_lending_fee`, `/app/input/lending_batches.csv`, `/app/input/borrowers.csv`, `/app/input/fee_accruals.jsonl`, `/app/output/securities_lending_fee_report.json`.

Author Anonymous tagged this **hard** data-processing task (go, data-processing, elt, batch-report, jsonl).

Time estimates: expert ~120.0 min, junior ~900.0 min.

Harbor timeouts: agent 1200.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5919ecf1-9cc7-4365-b8af-84f8f144df23_submission_2026-07-11T10_46_05.776Z.zip` is a task submission, not a Harbor job. 9 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
