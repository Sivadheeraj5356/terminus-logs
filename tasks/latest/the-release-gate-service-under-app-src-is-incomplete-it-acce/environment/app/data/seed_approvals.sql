-- approvals.mv.db seed. Schema first, then rows.

CREATE TABLE approved_keys (
    fingerprint VARCHAR(64) PRIMARY KEY,
    owner       VARCHAR(128) NOT NULL,
    status      VARCHAR(16)  NOT NULL,
    approved_at TIMESTAMP    NOT NULL,
    revoked_at  TIMESTAMP    NULL
);

CREATE TABLE exception_windows (
    id           INT           PRIMARY KEY,
    clause_id    VARCHAR(16)   NOT NULL,
    service_glob VARCHAR(128)  NOT NULL,
    starts_at    TIMESTAMP     NOT NULL,
    ends_at      TIMESTAMP     NOT NULL,
    approved_by  VARCHAR(128)  NOT NULL,
    approved_at  TIMESTAMP     NOT NULL
);

CREATE TABLE infra_registry (
    service_name VARCHAR(128) PRIMARY KEY,
    zone         VARCHAR(32)  NOT NULL
);

INSERT INTO approved_keys VALUES
    ('942607601B2B8AD9D8EB26A7574D706A78FF540D',
     'Gate Signer Alpha',   'active',
     TIMESTAMP '2026-01-01 00:00:00', NULL);

INSERT INTO approved_keys VALUES
    ('DF25FE22A636F090D6443D9B9561D6AF8BF3A3C3',
     'Gate Signer Bravo',   'rotated',
     TIMESTAMP '2026-01-01 00:00:00',
     TIMESTAMP '2026-03-10 08:00:00');

INSERT INTO approved_keys VALUES
    ('ECB920EA86252FA81CE4FBF623BC54402BB0A9DC',
     'Gate Signer Charlie', 'compromised',
     TIMESTAMP '2026-01-01 00:00:00',
     TIMESTAMP '2026-04-05 14:00:00');

INSERT INTO exception_windows VALUES
    (1, '§12.3', 'cache*',
     TIMESTAMP '2026-01-15 00:00:00',
     TIMESTAMP '2027-01-15 00:00:00',
     'ops-team',
     TIMESTAMP '2026-03-15 00:00:00');

INSERT INTO exception_windows VALUES
    (2, '§8.1', '*',
     TIMESTAMP '2026-01-01 00:00:00',
     TIMESTAMP '2027-01-01 00:00:00',
     'ops-team',
     TIMESTAMP '2026-02-01 00:00:00');

INSERT INTO exception_windows VALUES
    (3, '§14.5', 'bulk*',
     TIMESTAMP '2026-06-01 00:00:00',
     TIMESTAMP '2026-07-01 00:00:00',
     'ops-team',
     TIMESTAMP '2026-05-15 00:00:00');

INSERT INTO infra_registry VALUES ('db', 'infrastructure');
