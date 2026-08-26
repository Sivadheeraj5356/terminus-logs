# SQLite schema

Database file: path from `--db` or `FERT_DB` (default /app/data/fertigation.db).

Do not rename these tables.

## zones

| column | type |
|--------|------|
| zone_id | TEXT PRIMARY KEY |
| crop_label | TEXT NOT NULL |

## fertigation_batches

| column | type |
|--------|------|
| batch_id | TEXT PRIMARY KEY |
| zone_id | TEXT NOT NULL |
| opened_at_unix | INTEGER NOT NULL |
| closed_at_unix | INTEGER nullable |
| status | TEXT NOT NULL — OPEN or CLOSED |

## zone_state

| column | type |
|--------|------|
| zone_id | TEXT PRIMARY KEY |
| open_batch_id | TEXT nullable |

One OPEN batch per zone: when a batch opens, open_batch_id is set; when it closes, open_batch_id becomes NULL.

## dose_events

| column | type |
|--------|------|
| dose_id | TEXT PRIMARY KEY |
| batch_id | TEXT NOT NULL |
| ec_mS | REAL NOT NULL |
| ph | REAL NOT NULL |
| volume_ml | INTEGER NOT NULL |
| recorded_at_unix | INTEGER NOT NULL |

## daily_zone_volume

| column | type |
|--------|------|
| zone_id | TEXT NOT NULL |
| volume_date | TEXT NOT NULL — YYYY-MM-DD local greenhouse date |
| volume_ml | INTEGER NOT NULL |

Primary key (zone_id, volume_date). Optional cache; export recomputes daily totals from CLOSED batch dose rows.

## ingest_files

| column | type |
|--------|------|
| file_hash | TEXT PRIMARY KEY — SHA-256 hex of raw JSONL file bytes |
| ingested_at_unix | INTEGER NOT NULL |
| duplicate_skipped | INTEGER NOT NULL |

## fertigation_events

| column | type |
|--------|------|
| event_id | TEXT PRIMARY KEY |
| zone_id | TEXT NOT NULL |
| batch_id | TEXT |
| event_seq | INTEGER NOT NULL |
| event_type | TEXT NOT NULL |
| payload_json | TEXT NOT NULL |

Records applied events for cross-run dedupe.
