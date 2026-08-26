# Orchard feed threshold ledger rules (simple mode)

## CLI

```bash
canopyledger --profile <toml> --sensors <csv> --out <dir>
```

Writes `<dir>/s7_ledger.jsonl` (one JSON object per line).

## Settings TOML

- `orchard_id` string
- `base_temp_c` base temperature in Celsius for interval credit
- `ingest_unit` either `C` or `F` describing how CSV `temp` values are stored
- `bucket_anchor_epoch` integer Unix epoch anchoring daily window boundaries

## Precedence

Effective base temperature:

1. `ORCHARD_BASE_C` environment variable when set (parse as float)
2. otherwise `base_temp_c` from settings

Effective ingest unit:

1. `ORCHARD_INGEST_UNIT` environment variable when set (case-insensitive, `C` or `F`)
2. otherwise `ingest_unit` from settings

## Sensor CSV

Header `epoch_sec,sensor_id,temp,quality` then rows with:

- `epoch_sec` integer Unix seconds
- `sensor_id` string
- `temp` numeric temperature in the profile ingest unit
- `quality` either `OK` or `BAD`

Skip rows where `quality` is not `OK`.

## Unit conversion

When effective ingest unit is `F`, convert each reading to Celsius with `(temp - 32) * 5 / 9` before interval math.

## Windows

For a reading at `epoch`, window start is:

`bucket_anchor_epoch + floor((epoch - bucket_anchor_epoch) / 86400) * 86400`

For simple mode, readings before the anchor use the anchor bucket as window start.

Process readings in ascending `(epoch_sec, sensor_id)` order.

## Interval credit

For each accepted reading on a sensor within a bucket, interval hours are `(epoch - prev_epoch) / 3600` where `prev_epoch` is the previous accepted reading epoch on that sensor, or the bucket start if none yet in the bucket.

Interval credit equals the interval hours when `0 <= temp_c < base_temp_c`, otherwise zero.

Accumulate credited hours and count accepted samples per `(sensor_id, window_start)`.

Round `credit_hours` to four decimal places in output.

## Output schema

Each JSONL row:

- `sensor_id` string
- `bucket_epoch` integer window start epoch
- `credit_hours` float
- `sample_count` integer count of accepted readings in the window

## Output ordering

Sort rows by ascending `bucket_epoch`, then ascending `sensor_id`.
