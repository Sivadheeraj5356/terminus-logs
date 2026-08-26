# Facility snapshot

JSON object fields:

- `facility_id` (string)
- `assessment_epoch_unix` (integer unix seconds, UTC)
- `vessels` (array), each with:
  - `vessel_id` (string, unique)
  - `model_id` (string, must exist in catalog)
  - `cryogen` (string label; informational)
  - `level_liters` (number)
  - `pressure_psig` (number, gauge pressure)
  - `sensor_calibrated_until_unix` (integer)
- `placement_requests` (array), each with:
  - `request_id` (string)
  - `specimen_class` (`LN2` or `LHe`)
  - `min_hold_hours` (number)
  - `preferred_vessel_id` (string, may be empty)

Vessel rows in derived outputs are sorted by `vessel_id` ascending (byte-wise lexicographic).
