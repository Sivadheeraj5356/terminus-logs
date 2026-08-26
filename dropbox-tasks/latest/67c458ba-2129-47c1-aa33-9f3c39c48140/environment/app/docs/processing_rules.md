# Processing rules

These rules govern how the engine interprets the merged event timeline. They
apply uniformly to the bundled sample feeds and to any additional input directory
that follows the same schema.

## Timeline construction

1. Load every row from `admissions.csv`, `transfers.csv`, `procedures.csv`, and
   `discharges.csv`.
2. Sort the combined stream by `event_time`, then `event_seq`, then `event_id`.
3. Skip any row whose `event_id` has already been processed.

## Admissions

- Create a patient record on first successful admission.
- Assign the lexicographically first available bed in the target ward.
- Critical patients (`acuity_level` 1) prefer an available ICU bed when one exists.
- Reject when ward occupancy would exceed `max_beds` from `capacity.csv`.
- Reject with `icu_priority_violation` when a non-critical patient would occupy an
  ICU bed while any critical patient remains admitted and not discharged.

## Transfers

- Only `completed` transfers change patient location and bed assignment.
- `pending` and `partial` transfers are accepted but do not move the patient.
- Destination ward must have capacity and satisfy ICU rules.

## Procedures

- `completed` procedures increment `procedure_count` and add `duration_minutes`.
- `cancelled` procedures are ignored for totals.
- `scheduled` procedures have no effect until completed.

## Discharges

- Mark the patient discharged, record discharge time, free the assigned bed, and
  clear ward/bed fields.
- Reject discharges for unknown or already-discharged patients.

## Census at `as_of`

- A patient is `in_facility` at `as_of` when admitted on or before `as_of` and
  either not discharged or discharged after `as_of`.
- A patient with no discharge event remains `in_facility` when admitted on or
  before `as_of`.
- `peak_occupancy` is the maximum number of concurrently assigned beds while
  processing the timeline.
- `los_hours` uses whole hours between admission and discharge, or between
  admission and `as_of` when no discharge exists.

## Physical beds

- Beds marked `maintenance` in `beds.csv` cannot be assigned.
- Ward capacity limits come from `capacity.csv`, not from the raw bed inventory count.
