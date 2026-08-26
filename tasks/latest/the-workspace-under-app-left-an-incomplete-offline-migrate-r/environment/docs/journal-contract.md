# Migrate journal

`/app/state/migrate-journal.jsonl` is an append-only phase log. Phases include
`SNAPSHOT`, `STAGE`, `PROMOTE`, `COMMIT`, and `ABORT`.

On resume, if events exist after the last `COMMIT`, keep the prefix through
that `COMMIT`, then append a single `ABORT` with
`reason` exactly `interrupted_train_migrate` listing dropped phases. Do not
discard committed history. If the tip is already clean (ends at `COMMIT` or
already has a trailing `ABORT` for the incomplete suffix), resume is a no-op.

A successful seal ends by appending `SNAPSHOT`/`STAGE`/`PROMOTE`/`COMMIT`
for the current plan fingerprint.
