# Fertigation compliance rules

Profile fields live in /app/config/greenhouse-profile.json.

## EC drift integral

For each CLOSED batch, order dose events by `recorded_at_unix` ascending.

Let `target` = `target_ec_mS` from profile. For each dose `i`, `dev_i = abs(ec_mS_i - target)`.

### Lead-in segment

When the batch has at least one dose, add one segment from `opened_at_unix` to the first dose timestamp `t_1`:

- Find the most recent prior **CLOSED** batch on the same `zone_id` (by greatest `closed_at_unix` strictly before this batch's `opened_at_unix`).
- If that prior batch's `closed_at_unix` falls on the **same local calendar day** as this batch's `opened_at_unix` in `greenhouse_timezone`, set `ec_anchor` to the `ec_mS` of that prior batch's chronologically latest dose (maximum `recorded_at_unix`). Otherwise `ec_anchor = target`.
- `dev_anchor = abs(ec_anchor - target)`.
- Lead-in segment = `((dev_anchor + dev_1) / 2) * (t_1 - opened_at_unix)`.

When there are zero doses, the integral is 0 (no lead-in).

### Between doses

For consecutive doses `i` and `i+1` in time order:

`segment = ((dev_i + dev_{i+1}) / 2) * (t_{i+1} - t_i)`

`ec_drift_integral` is the sum of the lead-in segment (if any) plus all between-dose segments.

`ec_ok` is true when `ec_drift_integral <= max_ec_drift_integral`.

## pH gate

`ph_ok` is true when every dose `ph` value lies in the closed interval `[ph_min, ph_max]`. A single out-of-range dose fails the batch.

## Batch volume

`volume_ok` is true when the sum of `volume_ml` for doses in this batch only is `<= max_batch_volume_ml`.

## Daily zone volume

`daily_volume_ok` is evaluated when a batch closes. Use the local calendar date of `closed_at_unix` in `greenhouse_timezone`. Sum `volume_ml` from all doses belonging to CLOSED batches for that zone on that date (include the batch being closed). `daily_volume_ok` is true when that sum is `<= max_daily_volume_ml_per_zone`.

Daily totals are not accumulated on individual dose inserts. Recompute from CLOSED batch dose rows so totals survive replays on the same database file.

## Batch release

`batch_release_ok` = `ec_ok` AND `ph_ok` AND `volume_ok` AND `daily_volume_ok` AND `dose_count >= min_dose_count`.

`dose_count` is the number of `dose_events` rows for the batch.

## Batch close gate

`BATCH_CLOSE` events are rejected when the batch has fewer than `min_dose_count` dose rows. fert-ingest exits non-zero; stderr contains `insufficient doses` (see /app/docs/cli-contract.md).

## Zone batch state

One OPEN batch per zone. `BATCH_OPEN` is rejected when the zone already has an open batch.
