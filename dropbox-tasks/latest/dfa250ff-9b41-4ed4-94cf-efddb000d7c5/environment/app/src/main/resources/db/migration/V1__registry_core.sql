-- V1: model registry core tables.
CREATE TABLE model_run (
    run_id        VARCHAR(64)  NOT NULL PRIMARY KEY,
    model_name    VARCHAR(64)  NOT NULL,
    model_version VARCHAR(32)  NOT NULL,
    trained_at    TIMESTAMP    NOT NULL,
    champion      BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE feature_catalog (
    feature_id VARCHAR(64) NOT NULL PRIMARY KEY,
    family     VARCHAR(32) NOT NULL,
    monitored  BOOLEAN     NOT NULL
);
