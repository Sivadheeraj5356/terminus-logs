# Output contract (replay mode)

Replay mode writes three artifacts under the `--out` directory.

## s7_ledger.jsonl

One JSON object per line with keys:

```json
{
  "orchard_id": "north-ridge",
  "sensor_id": "A1",
  "bucket_epoch": 1704067200,
  "credit_hours": 1.2500,
  "sample_count": 2
}
```

- Sort by `bucket_epoch`, then `sensor_id`.
- `credit_hours` rounded to four decimals.
- Unix newlines.

## s7_audit.tsv

Tab-separated header:

```text
orchard_id	sensor_id	bucket_epoch	raw_samples	accepted_samples	tombstoned_samples	split_segments	input_hash
```

One row per `(sensor_id, bucket_epoch)` with ledger or audit activity.

- `raw_samples` — raw feed rows before revision collapse in that bucket.
- `accepted_samples` — winning OK readings whose timestamp bucket is this bucket.
- `tombstoned_samples` — winning deletes whose original or corrected timestamp bucket is this bucket.
- `split_segments` — interval pieces (credited or not) assigned to this bucket.
- `input_hash` — matches replay state.

Sort by `bucket_epoch`, then `sensor_id`.

## replay_state.json

```json
{
  "state_version": 2,
  "input_hash": "16 hex chars",
  "row_count": 12,
  "sensor_count": 3,
  "bucket_count": 4
}
```

Compatible state (version 2, matching `input_hash`) enables idempotent reruns. Missing, malformed, stale, or wrong-version state is ignored.

## Atomicity

Write through temporary files and rename. On malformed input or usage failure, do not leave successful partial `s7_ledger.jsonl`, `s7_audit.tsv`, or `replay_state.json`, and do not clobber prior valid outputs in the output directory.

## CLI exit codes

- `2` — usage errors (missing required flags)
- `1` — other failures (malformed manifest, bad feeds, I/O errors)
