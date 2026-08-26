# PAM faillock authentication enforcement contract

This document defines the lockout enforcement ledger emitted by `bayctl report`
for authentication security auditors. Access-control semantics and CLI stdout
strings live in `/app/docs/lock_rules.md`.

Grading inspects the binary at `/app/bin/bayctl` as it exists on disk; it does
not recompile from `/app` sources. Rebuild that path after code changes.

## Ledger schema

`/app/output/lock_ledger.json` is JSON with:

- `generated_from`: must be `baylock-lock-v2`
- `attempt_count`: total attempts recorded in runtime
- `failure_total`: authoritative failure count for the active principal
- `event_line_count`, `applied_count`, `rejected_count`: journal replay counters from projection
- `projection_digest`: lowercase SHA-256 hex over projection body fields
- `views`: array sorted by `view_id` then `principal`; each entry has `view_id`, `principal`, `failure_count`, `locked`
- `audits`: array sorted by `seq` ascending; each entry has `view_id`, `principal`, `actor_ref`, `seq`
- `ledger_digest`: lowercase SHA-256 hex

Both `host` and `ns` view rows must appear for the active principal on every ledger report.

## Audit schema

`/app/output/lock_audit.json` is JSON with:

- `generated_from`: must be `baylock-audit-v1`
- `batch_count`: imported batch count
- `journal_digest`: lowercase SHA-256 hex over journal provenance
- `projection_digest`: lowercase SHA-256 hex; after a successful rebuild must match the ledger's `projection_digest`
- `batches`: per-batch provenance rows
- `audit_digest`: lowercase SHA-256 hex

## Digest

`ledger_digest` / `audit_digest` hash the object **excluding** the digest field
itself, using Python-compatible canonical JSON:

```python
json.dumps(body, sort_keys=True, separators=(",", ":"))
```

For the ledger, the body includes `generated_from`, `attempt_count`, `failure_total`,
`event_line_count`, `applied_count`, `rejected_count`, `projection_digest`, **all**
`views` rows, and **all** `audits` rows.

## Persistence

Runtime authority lives in `/app/state/runtime.json`. Authoritative per-principal counters live
under `/app/state/auth/<principal>.tally`.
