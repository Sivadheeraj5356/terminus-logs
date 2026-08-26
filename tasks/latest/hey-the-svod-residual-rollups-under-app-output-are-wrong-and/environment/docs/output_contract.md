# Output contract

All outputs under `/app/output/`. LF line endings; exactly one trailing newline on CSV and JSONL files. CSV integer fields are unquoted decimal integers.

## Daily CSV (`residual_daily.csv`)

Header:

`workId,territory,dayLocal,medium,playCount,grossMicroCents,recoupedMicroCents,netMicroCents`

| column | rule |
| --- | --- |
| `playCount` | Sum of deduped play counts in the bucket |
| `grossMicroCents` | Sum of accruals in the bucket |
| `recoupedMicroCents` | Always `0` |
| `netMicroCents` | Equals `grossMicroCents` |

Omit rows where `playCount` is 0.

## Weekly CSV (`residual_weekly.csv`)

Derived from daily rows after daily aggregation completes.

Header:

`workId,territory,weekStartLocal,playCount,grossMicroCents,recoupedMicroCents,netMicroCents`

Group by `(workId, territory, weekStartLocal)`:

| column | rule |
| --- | --- |
| `playCount` | Sum of daily `playCount` |
| `grossMicroCents` | Sum of daily `grossMicroCents` |
| `recoupedMicroCents` | Always `0` |
| `netMicroCents` | Sum of daily `netMicroCents` |

**Cross-artifact invariant:** weekly `grossMicroCents` equals the sum of daily `grossMicroCents` for the same `(workId, territory, weekStartLocal)`.

## Escrow JSONL (`escrow_ledger.jsonl`)

Body line keys in order: `workId`, `territory`, `periodMonth`, `participantId`, `amountMicroCents`, `catalogIndex`.

Footer line keys in order: `type`, `periodMonth`, `poolTotalMicroCents`, `lineCount`, `prevHash`, `entryHash`.

- JSON must be compact: no spaces outside string values and one JSON object per line.
- `type` is always `footer`
- `poolTotalMicroCents` = sum of body `amountMicroCents`
- `lineCount` = count of body lines
- `prevHash` = 64 ASCII zero digits for the bundled single-footer run
- `entryHash` = lowercase hex HMAC-SHA256 of the canonical message keyed by `ESCROW_AUDIT_SECRET` (default `residual-escrow-key`)

Canonical message: `periodMonth|poolTotalMicroCents|lineCount|prevHash` (single ASCII pipes, no spaces).

Body lines precede the footer. One footer per run.

**Cross-artifact invariant:** `poolTotalMicroCents` equals the sum of participant allocations after recoupment and split for `periodMonth`.

## Shape validator

`/app/internal/validate/pool_validator.go` checks column headers and JSON key presence only. It does not verify totals, ordering, or HMAC correctness.
