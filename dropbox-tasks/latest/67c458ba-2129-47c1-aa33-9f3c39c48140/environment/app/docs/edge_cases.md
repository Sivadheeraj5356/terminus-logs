# Edge cases represented in sample data

The bundled CSV feeds under `data/` exercise the following scenarios. They are
representative examples of production traffic patterns rather than an exhaustive
catalog of every possible input combination.

## Timestamp ties

Multiple events share the same `event_time` (for example concurrent admissions).
Processing order must follow `event_seq`, then `event_id`, because bed availability
and rejections depend on earlier events at the same clock second.

## Ward capacity limits

`capacity.csv` may allow fewer concurrent patients than the number of physical beds
listed in `beds.csv` (for example when beds are in maintenance). Admissions that
would exceed the configured ward limit are rejected even when empty physical beds
appear to exist elsewhere.

## ICU priority

Critical patients receive ICU beds when available. Non-critical patients cannot
occupy ICU beds while any critical patient remains admitted and not discharged,
including during transfer attempts into ICU wards.

## Cancelled procedures

Procedure rows marked `cancelled` must not affect `procedure_count`,
`procedure_minutes`, or summary procedure totals. Completed and cancelled rows for
the same patient can coexist.

## Partial and pending transfers

Transfers marked `partial` or `pending` are recorded in the feed but must not change
the patient's ward or bed assignment. Only `completed` transfers release the source
bed and allocate at the destination.

## Duplicate event identifiers

The same `event_id` may appear on more than one CSV row (for example resubmitted
feeds). Only the first occurrence in the ordered timeline is applied; later rows
are ignored without generating a rejection entry.

## Missing discharge events

Patients can remain in the facility beyond their last clinical event when no row
exists in `discharges.csv`. Census metrics at `as_of` must still count those
patients as `in_facility` and include them in ward occupancy.

## Re-admission after rejection

A patient identifier may appear on a rejected admission row and later on a
successful admission row with a different `event_id`. Only successful admissions
create census rows.

## Discharge before census

Patients discharged before `as_of` appear with status `discharged`, null ward/bed
fields, and length-of-stay ending at the discharge timestamp.
