# Observation contract

Each JSONL object has string fields `id`, `indicator`, `source`, `contractor`, `malware`, `beacon`, `toolcell`, `actor`, and integer fields `start`, `end`, `reliability_bp`. The interval is half-open `[start,end)`, with `start < end`. IDs are unique after primary and optional fixture lines are merged. Strings are compared bytewise after ASCII lowercase normalization and surrounding whitespace removal.

The policy object has `minimum_reliability_bp`, `edge_threshold_bp`, `high_confidence_bp`, `medium_confidence_bp`, `maintenance_epochs`, `contractor_aliases`, and `commodity_beacons`. Maintenance epochs are objects with `toolcell`, `start`, and `end`. Alias groups are arrays of names and are transitively unioned. Commodity beacons are exact normalized strings.
