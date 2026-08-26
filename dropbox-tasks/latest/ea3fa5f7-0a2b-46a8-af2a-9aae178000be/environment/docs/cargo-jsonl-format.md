# cargo.jsonl format

Each mission directory contains cargo.jsonl with one JSON object per line. Blank lines are ignored.

Required fields per cargo row:

| Field | Type | Notes |
|-------|------|-------|
| cargo_id | string | Unique identifier |
| dock_min | number | Base berth clock in minutes |
| tide_ms | integer | Signed tide offset in milliseconds (negative values are valid) |
| base_min | number | Base transfer duration before wave scaling |
| wave_m | number | Wave multiplier for transfer duration |
| psi | number | Pressure rating for berth compatibility |
| lane | string | Lane label compared to habitat primary_lane |
| priority | number | Used in score formula |
| needs_rov | boolean | When true, cargo requires ROV slot reservation |
| m3 | number | Volume in cubic meters |
| cold | boolean | When true, volume counts toward cold_cap_m3 |
| o2 | integer | Oxygen priority tier (lower number = higher priority) |

Optional fields such as zone may appear in input but must not be copied into tide snapshot acts.

After loading, sort cargo rows by cargo_id ascending before any hash or snapshot computation.

Preserve tide_ms sign exactly as stored. Do not take absolute value.
