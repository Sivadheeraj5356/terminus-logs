# Replay manifest format

## Example

```toml
manifest_version = 2
orchard_id = "north-ridge"
profile = "profiles/base.toml"
sensor_registry = "registries/sensors.csv"
readings = ["feeds/day1.csv", "feeds/day2.csv"]
corrections = ["corrections/day1.patch.csv"]
state_policy = "strict"
```

## Rules

- `manifest_version` must be `2`.
- `profile`, `sensor_registry`, `readings`, and `corrections` paths resolve relative to the manifest file.
- Paths must remain under the manifest directory or `/app/environment/fixtures`.
- `readings` requires at least one file.
- `corrections` may be empty.
- Unknown manifest keys are malformed.
- Duplicate manifest keys are malformed.
- Missing required fields are malformed.

## Sensor registry CSV

```text
sensor_id,unit,offset_c,active_from,active_until
```

- `sensor_id` unique and non-empty.
- `unit` is `C`, `F`, or blank (use effective profile/env ingest unit).
- `offset_c` decimal Celsius offset applied after unit conversion.
- `active_from` / `active_until` Unix seconds or blank; reading accepted only when `active_from <= epoch < active_until` when bounds present.

## Reading feed

Headers:

```text
epoch_sec,sensor_id,temp,quality
epoch_sec,sensor_id,temp,quality,reading_id,rev
```

- `reading_id` non-empty and `rev` positive integer when present.
- Without `reading_id`, derive `<feed_index>:<physical_row_number>` with implicit revision `1`.
- Malformed numeric fields fail the run.

## Correction CSV

```text
op,reading_id,epoch_sec,sensor_id,temp,quality,rev
```

- `op` is `upsert` or `delete`.
- `rev` positive integer.
- Highest revision per `reading_id` wins across all feeds and corrections.
- Duplicate `(reading_id, rev)` is malformed.
- Winning `delete` tombstones the reading.
- Winning `upsert` includes all reading fields.
- Non-OK winning readings excluded after collapse.

## Bucket-boundary splitting (replay)

Unlike simple mode, replay splits intervals across daily buckets anchored at `bucket_anchor_epoch`:

- Interval from previous accepted reading epoch or containing bucket start.
- Split across every bucket boundary crossed.
- Credit each piece using ending reading calibrated temperature.
- `sample_count` only in bucket containing reading timestamp.
- Pre-anchor timestamps use `anchor + floor((epoch-anchor)/86400)*86400` without clamping to anchor.

## Calibration order

1. Registry unit if non-blank, else `ORCHARD_INGEST_UNIT`, else profile `ingest_unit`.
2. Convert `F` to Celsius.
3. Add registry `offset_c`.
4. Credit when `0 <= temp_c < effective_base_c`.

## Input hash

FNV-1a64 over manifest bytes plus referenced file bytes in order: profile, registry, readings (manifest order), corrections (manifest order). Encoded as 16 lowercase hex characters.
