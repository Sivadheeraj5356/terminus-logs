The clinical operations team needs a Rust CLI under `/app` that rebuilds hospital census and procedure analytics from CSV event feeds. Build and run:

```bash
cd /app && cargo build --release --locked
cd /app && ./target/release/hospital_analytics --input-dir /app/data --output /app/output/analytics_report.json
```

Inputs under `/app/data` include `admissions.csv`, `transfers.csv`, `beds.csv`, `procedures.csv`, `discharges.csv`, and `capacity.csv`. Schemas, processing rules, and edge-case notes are documented under `/app/docs/` and `/app/data/README.md`.

Write `/app/output/analytics_report.json` with top-level keys `as_of`, `summary`, `patients`, `ward_occupancy`, and `rejected_events`. Summary includes `total_admissions`, `active_patients`, `discharged_patients`, `total_procedures`, `peak_occupancy`, and `rejected_event_count`. Each patient row includes `patient_id`, `acuity_level`, `current_ward`, `bed_id`, `status` (`in_facility` or `discharged`), `procedure_count`, `procedure_minutes`, and `los_hours` (whole hours from admission to discharge, or to `as_of` when no discharge exists). Each ward occupancy row includes `ward`, `occupied`, and `capacity`. Emit `ward_occupancy` rows only for wards with `occupied > 0` at the report `as_of` timestamp. Omit wards whose occupied count is zero. Do not emit zero-occupancy placeholder rows. Each rejected row includes `event_id`, `event_time`, `event_seq`, and `reason`.

Merge every row from all event CSV files into one timeline ordered by `event_time`, then `event_seq`, then `event_id`. Duplicate `event_id` values after the first processed occurrence are ignored silently. Admissions create patients and assign the first available bed in the target ward; reject with `ward_at_capacity` when ward occupancy would exceed `max_beds` from `capacity.csv`, and reject with `icu_priority_violation` when a non-critical patient (`acuity_level` greater than 1) would occupy an ICU bed while any critical (`acuity_level` 1) patient remains admitted and not discharged. Transfers with status `completed` move patients when destination capacity and ICU rules allow; `pending` and `partial` transfers leave the patient in the source ward. Completed procedures increment counts and minutes; `cancelled` procedures are excluded from totals; `scheduled` procedures have no effect. Discharges free beds and mark patients discharged; patients with no discharge event remain `in_facility` at `as_of` when admitted on or before that timestamp. Reject unknown patients and already-discharged patients where applicable.

Sort `patients` by `patient_id`. Sort emitted `ward_occupancy` rows by `ward`. Sort `rejected_events` by `event_time`, then `event_seq`, then `event_id`. Re-running against the same inputs must produce identical output.

The verifier may run the tool against additional input directories that follow the same schema. Compute the report from the current input files; do not hardcode the sample fixture values.
