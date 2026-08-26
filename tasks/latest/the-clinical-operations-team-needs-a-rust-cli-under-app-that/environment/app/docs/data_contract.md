# Data contract

## Census snapshot

`as_of` is an ISO-8601 UTC timestamp defined in `/app/data/README.md`. All
`in_facility` statuses and ward occupancy counts are evaluated at this instant.

## Event CSV files

Each event file shares the columns `event_time`, `event_seq`, and `event_id`.
Additional columns are defined per file in `data/README.md`.

| File | Row meaning |
| --- | --- |
| `admissions.csv` | Patient arrival with acuity and preferred ward |
| `transfers.csv` | Ward movement request with completion status |
| `procedures.csv` | Clinical procedure with duration and status |
| `discharges.csv` | Patient departure with disposition |

## Static configuration

| File | Row meaning |
| --- | --- |
| `beds.csv` | Physical bed inventory, ICU flag, maintenance flag |
| `capacity.csv` | Maximum concurrent patients per ward |

## Output JSON

Path: `/app/output/analytics_report.json`

### Top level

| Key | Type | Description |
| --- | --- | --- |
| `as_of` | string | Census snapshot timestamp |
| `summary` | object | Aggregate metrics |
| `patients` | array | One object per admitted patient |
| `ward_occupancy` | array | Occupied and capacity counts by ward at `as_of` |
| `rejected_events` | array | Events that could not be applied |

### `summary`

| Key | Type |
| --- | --- |
| `total_admissions` | integer |
| `active_patients` | integer |
| `discharged_patients` | integer |
| `total_procedures` | integer |
| `peak_occupancy` | integer |
| `rejected_event_count` | integer |

### `patients[]`

| Key | Type | Notes |
| --- | --- | --- |
| `patient_id` | string | |
| `acuity_level` | integer | 1 critical, 2 urgent, 3 routine |
| `current_ward` | string or null | Ward at `as_of` when in facility |
| `bed_id` | string or null | Assigned bed at `as_of` when in facility |
| `status` | string | `in_facility` or `discharged` |
| `procedure_count` | integer | Completed procedures only |
| `procedure_minutes` | integer | Sum of completed procedure durations |
| `los_hours` | integer | Whole hours from admission to discharge or `as_of` |

### `ward_occupancy[]`

Emit rows only for wards with `occupied > 0` at `as_of`. Omit wards whose
occupied count is zero. Do not emit zero-occupancy placeholder rows.

| Key | Type |
| --- | --- |
| `ward` | string |
| `occupied` | integer |
| `capacity` | integer |

### `rejected_events[]`

| Key | Type |
| --- | --- |
| `event_id` | string |
| `event_time` | string |
| `event_seq` | integer |
| `reason` | string |

Documented rejection reasons include `ward_at_capacity`, `icu_priority_violation`,
`no_available_bed`, `unknown_patient`, `patient_discharged`, `already_discharged`,
and `duplicate_admission`.

## Sorting

- `patients`: ascending `patient_id`
- `ward_occupancy`: ascending `ward` (emitted occupied-only rows only)
- `rejected_events`: ascending `event_time`, then `event_seq`, then `event_id`
