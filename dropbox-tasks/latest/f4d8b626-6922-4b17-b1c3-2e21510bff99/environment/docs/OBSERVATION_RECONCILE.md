# Observation reconcile

Input: resolved artifact with winning reports per lane plus original observations from staging.

1. Build a map of dive_lane to winning report calibration_valid.
2. Exclude observations whose dive_lane winning report has calibration_valid false. Lanes missing from the map are excluded.
3. Sort surviving observations by timestamp_utc ascending.
4. anchor_obs_id is the obs_id of the earliest observation (by timestamp) with obs_type HYDROTHERMAL_VENT. If none, anchor_obs_id is empty string.
5. feature_links: walk surviving observations in timestamp order. Skip the first observation. For each later observation, scan all earlier observations in reverse timestamp order. If any earlier observation shares the same dive_lane, links_to is the obs_id of the nearest such earlier observation. If no earlier observation shares the dive_lane, links_to is the obs_id of the immediately previous observation in global timestamp order (the observation at index minus one).

Reconciled output fields:
- expedition_id
- anchor_obs_id
- observation_count
- observations (timestamp order, full observation objects)
- feature_links (array of {obs_id, links_to})
