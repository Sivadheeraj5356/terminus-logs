# Atlas export

Input: reconciled observations artifact and policy path (read for validation only).

export-atlas loads dive_lanes from /app/state/{expedition_id}-resolved.json written by resolve-precedence. It must not re-run precedence arbitration from the dive staging snapshot. If the resolved state file is missing, exit 1 with RESOLVED_STATE_MISSING.

export-atlas loads reconcile_bind from /app/state/{expedition_id}-reconciled.json for expedition_seal per EXPEDITION_SEAL.md. If the reconciled state file is missing, exit 1 with RECONCILED_STATE_MISSING.

Atlas JSON fields:
- expedition_id
- anchor_obs_id
- observation_count
- observations: sorted by obs_id ascending (each includes obs fields only, no links_to)
- dive_lanes: array of winning report objects sorted by dive_lane ascending
- atlas_witness: see WITNESS_HASH.md
- expedition_seal: see EXPEDITION_SEAL.md
