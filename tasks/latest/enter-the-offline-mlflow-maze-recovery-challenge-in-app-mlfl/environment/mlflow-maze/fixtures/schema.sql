PRAGMA journal_mode = DELETE;
PRAGMA foreign_keys = OFF;

CREATE TABLE experiments (
    experiment_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL
);

CREATE TABLE runs (
    run_uuid TEXT PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL,
    start_time INTEGER,
    end_time INTEGER
);

CREATE TABLE params (
    run_uuid TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE metrics (
    run_uuid TEXT NOT NULL,
    key TEXT NOT NULL,
    value REAL NOT NULL,
    timestamp INTEGER NOT NULL,
    step INTEGER NOT NULL
);

CREATE TABLE tags (
    run_uuid TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE INDEX params_run_key ON params(run_uuid, key);
CREATE INDEX metrics_run_key ON metrics(run_uuid, key, timestamp);
CREATE INDEX tags_run_key ON tags(run_uuid, key);
CREATE INDEX runs_experiment ON runs(experiment_id);
