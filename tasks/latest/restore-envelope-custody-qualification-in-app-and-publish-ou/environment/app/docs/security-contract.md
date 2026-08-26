# Security contract

- Authority is evaluated at each object's `custody_epoch`.
- Rewrap heads follow signed journal lineage, not wall-clock ordering.
- Threshold recovery counts distinct `organization_id` values with valid share evidence.
- v1 AAD binds `ecrq/v1/<storage_name>`; v2 binds `ecrq/v2/<logical_path>/<object_id>`.
- Evidence snapshots hash manifest, authority, journal, objects, envelopes, and shares.
- Checkpoints bind to the complete snapshot digest and invalidate on any evidence change.
- Publication stages privately then atomically installs the recovery set.
