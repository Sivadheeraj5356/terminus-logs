# JSONL fertigation event format

Each line is one JSON object. Required on every line:

| field | type | required |
|-------|------|----------|
| event_type | string | yes — ZONE_REGISTER, BATCH_OPEN, DOSE_TICK, BATCH_CLOSE |
| event_seq | integer | yes — apply order key within the file |
| line_crc | string | yes — four uppercase hex digits |

## ZONE_REGISTER

| field | type |
|-------|------|
| zone_id | string |
| crop_label | string |

## BATCH_OPEN

| field | type |
|-------|------|
| zone_id | string — must be in profile zone_ids |
| batch_id | string |
| opened_at_unix | integer |

## DOSE_TICK

| field | type |
|-------|------|
| batch_id | string — must reference an OPEN batch |
| ec_mS | number |
| ph | number |
| volume_ml | integer |
| recorded_at_unix | integer — strictly increasing per batch |

## BATCH_CLOSE

| field | type |
|-------|------|
| batch_id | string |
| closed_at_unix | integer |

## line_crc

CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over UTF-8 bytes of canonical JSON for the line **without** the `line_crc` field.

Canonical JSON rules:

- Include every field from the line except `line_crc`.
- Sort object keys lexicographically.
- Use compact encoding with no extra spaces.
- **Preserve raw JSON number spelling from the line.** Each value token is copied verbatim from the JSONL line (`2` and `2.0` produce different CRC inputs). Do not recompute CRC with `JSON.stringify`, Python `json.dumps`, or any float re-encoding.
- `fert-ingest` builds the CRC body from line bytes via `json.RawMessage` (Go), matching the spelling on disk.

Shipped public and hidden JSONL fixtures use whole-number floats as JSON integers (`2`, `6`) in sorted compact lines.

## Ingest semantics

`fert-ingest` applies lines in **ascending event_seq** order, not physical file order. The ingest runs in a single SQLite transaction; a bad `line_crc` or invalid line aborts the whole ingest with no partial rows.

Idempotent replay: when the SHA-256 hash of the raw file bytes already exists in `ingest_files`, exit 0 without inserting duplicate events.

Duplicate event_id rows within a replay on the same database are skipped and counted in ingest stats.

Errors exit non-zero with a message on stderr.
