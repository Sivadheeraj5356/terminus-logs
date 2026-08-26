# Hold spine ledger

Bind materializes /app/state/hold-spine-ledger.json after peak capture. The ledger flattens every HOLD profile from dsc-peak-capture.json in batch_id ascending order, preserving each batch hold_profiles array order, and assigns contiguous spine_seq integers starting at 1.

Schema hold-spine-ledger-v1 top-level keys are schema, rows, and spine_digest only. Each row carries spine_seq, batch_id, polymorph, effective_hold_s, and temp_c.

spine_digest is SHA-256 over newline-joined lines
spine_seq|batch_id|polymorph|effective_hold_s|temp_c
in ascending spine_seq order with no trailing spaces.

Emit must load the ledger, recompute the digest from rows, and confirm it equals both the stored spine_digest and a rebuild from the on-disk peak capture. Emit must refuse to publish when the ledger is missing or digests diverge.

phase_seal preimage in /app/docs/walk-seal-bind.md includes spine_digest as the fifth pipe-separated field.
