# Ocean Expedition Log (OEL) format

Top-level JSON object fields:
- expedition_id: string
- reports: array of report objects
- observations: array of observation objects

Bundle files may begin with a UTF-8 byte order mark. Strip one leading U+FEFF character before parsing JSON.

Report object fields:
- report_id: string
- dive_lane: string
- confidence_rank: unsigned integer (lower is more trusted)
- revision: unsigned integer
- supersedes: string report_id or null
- calibration_valid: boolean

Observation object fields:
- obs_id: string
- dive_lane: string
- timestamp_utc: ISO-8601 UTC string ending with Z
- obs_type: string
- depth_m: integer meters
- feature_code: string
- instrument_id: string
