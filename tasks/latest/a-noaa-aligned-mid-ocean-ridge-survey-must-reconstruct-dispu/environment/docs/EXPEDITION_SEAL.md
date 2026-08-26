# Expedition seal

expedition_seal seals the atlas export to the persisted reconcile bind.

Compute expedition_seal per BIND_CRC.md expedition_seal section.

export-atlas must read reconcile_bind from /app/state/{expedition_id}-reconciled.json written by reconcile-observations. If the reconciled state file is missing, exit 1 with RECONCILED_STATE_MISSING.

The atlas JSON includes expedition_seal as a top-level field alongside atlas_witness.
