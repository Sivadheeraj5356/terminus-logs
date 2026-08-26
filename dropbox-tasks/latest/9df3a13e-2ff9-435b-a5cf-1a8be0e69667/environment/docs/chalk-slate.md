# Chalk slate

## Purpose

Operators chalk a match ticket before allotment. Allotment must read the ticket on disk and must not re-read /app/data/disk-packages.json during the allot stage.

## Path

Default chalk path: /app/state/chalk-slate.json

## Schema

- schema: always "wax-chalk-slate/v1"
- court_id: string
- lots: array copied from the wax manifest, sorted by lot id ascending, each object keeping id, lanes (lanes sorted ascending), score, weight
- lots_digest: lowercase hex SHA-256 of compact UTF-8 JSON equal to json.dumps(lots, separators=(",", ":"), ensure_ascii=True) after the sort/normalize above
- chalk_epoch: integer; start at 1 when /app/state/chalk-epoch is missing or empty; otherwise read the integer from /app/state/chalk-epoch and use that value; after a successful chalk write, persist chalk_epoch + 1 into /app/state/chalk-epoch
- court_digest: lowercase hex SHA-256 of compact UTF-8 JSON of the court object with lanes sorted by lane id and keys court_id then lanes; each lane object keys ordered id, band, mutex_group

## Binding

The allot stage refuses to run when:

- chalk slate is missing
- slate schema is not wax-chalk-slate/v1
- lots_digest does not recompute from the slate lots field
- court_digest does not match a fresh digest of the court file passed to allot

On success the ledger copies lots_digest and chalk_epoch from the slate.

The chalk slate is the match ticket between the chalk command and the allot command.

Digests are SHA-256 hex digests. Verifier reference math may use the same SHA-256 construction as hashlib.sha256 over compact UTF-8 JSON.

Compact digests can be mirrored by /app/scripts/digest_mirror.py which uses hashlib.sha256.
