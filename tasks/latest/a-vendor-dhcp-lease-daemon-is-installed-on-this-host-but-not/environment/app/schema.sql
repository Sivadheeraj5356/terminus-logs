PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS pools (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cidr          TEXT NOT NULL,
    lease_secs    INTEGER NOT NULL,
    network       INTEGER NOT NULL,
    broadcast     INTEGER NOT NULL,
    prefix        INTEGER NOT NULL,
    created_ms    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    pool_id   INTEGER NOT NULL,
    ip        INTEGER NOT NULL,
    client_id TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS leases (
    ip          INTEGER PRIMARY KEY,
    pool_id     INTEGER NOT NULL,
    client_id   TEXT NOT NULL,
    expires_ms  INTEGER NOT NULL,
    created_ms  INTEGER NOT NULL,
    state       TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS declines (
    ip       INTEGER PRIMARY KEY,
    pool_id  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms      INTEGER NOT NULL,
    event      TEXT NOT NULL,
    pool_id    INTEGER,
    ip         INTEGER,
    client_id  TEXT
);
