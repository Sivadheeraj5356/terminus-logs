# SQLite checkpoint ledger

The ledger lives at `/app/ops/state/export_ledger.sqlite`. It contains a `checkpoint` table with these columns:

- `partition_id text primary key`
- `sequence integer not null`
- `status text not null`, either `export` or `omit`
- `cursor_start text not null`
- `cursor_end text not null`
- `prev_cursor text not null`
- `digest_hex text not null`
- `omission_reason text`
- `omission_digest_hex text`
- `service_generation text not null`
- `batch_id text not null`
- `terminal integer not null`

There is one terminal row for every partition-bearing cursor event. Exported rows have empty omission fields. Omitted rows have `status = omit`, `omission_reason` from the cursor event, and `omission_digest_hex` using the digest formula in `manifest.md`.
