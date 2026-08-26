PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ledger_verifications (
    batch_id    TEXT PRIMARY KEY,
    row_count   INTEGER NOT NULL,
    chain_ok    INTEGER NOT NULL CHECK (chain_ok IN (0, 1)),
    verified_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_store (
    batch_id        TEXT NOT NULL,
    account_id      TEXT NOT NULL,
    tx_count        INTEGER NOT NULL,
    total_amount    INTEGER NOT NULL,
    avg_amount      REAL NOT NULL,
    foreign_ratio   REAL NOT NULL,
    max_amount      INTEGER NOT NULL,
    populated_at    TEXT NOT NULL,
    PRIMARY KEY (batch_id, account_id)
);

CREATE TABLE IF NOT EXISTS scoring_jobs (
    job_id      TEXT PRIMARY KEY,
    batch_id    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    created_at  TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS scoring_predictions (
    job_id          TEXT NOT NULL,
    account_id      TEXT NOT NULL,
    risk_score      REAL NOT NULL,
    prediction_hmac TEXT NOT NULL,
    signed_at       TEXT NOT NULL,
    PRIMARY KEY (job_id, account_id),
    FOREIGN KEY (job_id) REFERENCES scoring_jobs(job_id)
);
