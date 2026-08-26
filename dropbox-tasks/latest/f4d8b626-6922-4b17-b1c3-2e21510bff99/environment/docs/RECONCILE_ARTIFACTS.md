# Reconcile artifacts

reconcile-observations output fields:
- expedition_id
- anchor_obs_id
- observation_count
- observations (timestamp order, full observation objects)
- feature_links (array of {obs_id, links_to})
- replay_seq (always 2 after successful reconcile)
- reconcile_bind

reconcile_bind follows BIND_CRC.md reconcile_bind section.

Also mirrors the full reconciled artifact to /app/state/{expedition_id}-reconciled.json. export-atlas reads reconcile_bind from this on-disk snapshot for expedition_seal per EXPEDITION_SEAL.md.
