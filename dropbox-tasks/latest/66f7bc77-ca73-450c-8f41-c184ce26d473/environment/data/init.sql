PRAGMA foreign_keys = ON;

CREATE TABLE candidates (
    candidate_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    sklearn_pin TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    accuracy REAL NOT NULL,
    macro_f1 REAL NOT NULL,
    latency_p99_ms REAL NOT NULL,
    canary_fixture TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    eval_completed_at TEXT NOT NULL,
    holdout_samples INTEGER NOT NULL
);

INSERT INTO candidates VALUES (
    'CAND-2026-042',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-017',
    'rf-spam-v2',
    '1.4.2',
    'sha256:fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654',
    0.905,
    0.870,
    38.0,
    '/app/fixtures/canary-runs/batch-017.json',
    'batch-017',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-099',
    'rf-spam-v4',
    '1.5.0',
    'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeee',
    0.900,
    0.850,
    55.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-099',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-088',
    'rf-spam-v3',
    '9.9.9',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-050',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    50.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-071',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.880,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-072',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.908,
    0.890,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-073',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.910,
    0.875,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-051',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    58.1,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-091',
    'rf-spam-v3',
    '9.9.9',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    55.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-099',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-055',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.8866,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-074',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-074',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-060',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-03-01',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-061',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-01',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-092',
    'rf-spam-v4',
    '1.5.0',
    'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeee',
    0.900,
    0.850,
    50.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-099',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-044',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    45.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-056',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.8864,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-062',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-03-31',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-004',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    50.0,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-04',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-093',
    'rf-spam-v3',
    '1.4.2',
    'sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    80
);

INSERT INTO candidates VALUES (
    'CAND-2026-094',
    'rf-spam-v3',
    '1.4.2',
    'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);

INSERT INTO candidates VALUES (
    'CAND-2026-045',
    'rf-spam-v3',
    '1.4.2',
    'SHA256:A1B2C3D4E5F6789012345678ABCDEF0123456789ABCDEF0123456789ABCD',
    0.918,
    0.891,
    42.5,
    '/app/fixtures/canary-runs/batch-042.json',
    'batch-042',
    '2026-04-10',
    1200
);
