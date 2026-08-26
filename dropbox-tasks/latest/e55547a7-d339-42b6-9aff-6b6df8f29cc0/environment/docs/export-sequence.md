# Export sequence

Written to /app/state/export-sequence.json by cascade-export.

Fields:
- run_seq: monotonically increasing integer, starting at 1 on first run
- atlas_hash: the atlas_hash from the current run
- ledger_hash: the ledger_hash from the current run

On repeat runs with unchanged inputs, atlas_hash and ledger_hash must remain stable while run_seq increments.
