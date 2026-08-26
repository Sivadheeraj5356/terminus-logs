# habitat profile

Each mission directory contains habitat.json describing berth capacity, ROV bays, and policy limits.

Top-level fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| schema_version | integer | yes | Must be 1 |
| mission_label | string | yes | Captured on export-bind.json during ingest |
| primary_lane | string | yes | Lane label for needs_rov inference |
| rov_lead_min | number | yes | ROV must finish this many minutes before berth_start |
| rov_turn_min | number | yes | Turnaround added after each ROV slot |
| rov_bays | integer | yes | Count of ROV bays (R1 through RN) |
| berth_gap_min | number | yes | Minimum gap between consecutive loads on same berth |
| psi_gap | number | yes | Pressure difference threshold for gap buffering |
| berths | array | yes | Berth specifications |
| cold_cap_m3 | number | yes | Maximum cold-chain volume |
| surge_cargo_id | string | no | Cargo scheduled last after all others |
| lane_window_min | object | no | Per-lane minutes added to berth_start; see lane-window-offset.md |
| berth_clock_band | object | no | min/max clamp on the tide berth clock; see berth-clock-band.md |
| rov_bays_offline | array | no | One-based ROV bays out of service; see rov-bays-offline.md |
| handoff_pad_min | number | no | Minutes added on gap_used handoffs; see transfer-cert.md |
| witness_salt | string | no | Optional mission metadata, included in mission_hash |

Each berth object:

| Field | Type |
|-------|------|
| berth_id | string |
| psi_min | number |
| psi_max | number |

## mission_hash

Compute mission_hash as SHA-256 hex digest of compact JSON (separators comma-colon, sort_keys true):

```
{"cargo": [<sorted cargo rows by cargo_id>], "habitat": {<habitat fields except schema_version, keys sorted>}}
```

The habitat object in the hash excludes schema_version only. All other habitat keys, including witness_salt when present, are included in sorted order.
