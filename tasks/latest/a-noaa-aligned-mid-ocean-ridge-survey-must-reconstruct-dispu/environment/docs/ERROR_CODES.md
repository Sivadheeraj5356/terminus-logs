# Error codes

DIVE_READ_ERROR — bundle path unreadable
DIVE_FORMAT_ERROR — bundle JSON invalid or missing required fields
STAGING_PARSE_ERROR — staging JSON invalid
RESOLVED_STATE_MISSING — /app/state/{expedition_id}-resolved.json absent during export-atlas
RESOLVED_PARSE_ERROR — resolved JSON invalid
RECONCILE_PARSE_ERROR — reconciled JSON invalid
RECONCILED_STATE_MISSING — /app/state/{expedition_id}-reconciled.json absent during export-atlas
REPLAY_MISMATCH — resolved.replay_seq is not 1 during reconcile-observations
POLICY_READ_ERROR — policy path unreadable
