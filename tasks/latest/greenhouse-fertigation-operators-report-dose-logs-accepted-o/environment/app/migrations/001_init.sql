CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS zones (
  zone_id TEXT PRIMARY KEY,
  crop_label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fertigation_batches (
  batch_id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  opened_at_unix INTEGER NOT NULL,
  closed_at_unix INTEGER,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zone_state (
  zone_id TEXT PRIMARY KEY,
  open_batch_id TEXT
);

CREATE TABLE IF NOT EXISTS dose_events (
  dose_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL,
  ec_mS REAL NOT NULL,
  ph REAL NOT NULL,
  volume_ml INTEGER NOT NULL,
  recorded_at_unix INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_zone_volume (
  zone_id TEXT NOT NULL,
  volume_date TEXT NOT NULL,
  volume_ml INTEGER NOT NULL,
  PRIMARY KEY (zone_id, volume_date)
);

CREATE TABLE IF NOT EXISTS ingest_files (
  file_hash TEXT PRIMARY KEY,
  ingested_at_unix INTEGER NOT NULL,
  duplicate_skipped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fertigation_events (
  event_id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  batch_id TEXT,
  event_seq INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
