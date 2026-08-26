-- V4: cohort register used by the underwriting monitoring board.
CREATE TABLE cohort_register (
    cohort_id      VARCHAR(64) NOT NULL PRIMARY KEY,
    display_name   VARCHAR(64) NOT NULL,
    status         VARCHAR(16) NOT NULL,
    legacy_alias   VARCHAR(32),
    effective_from DATE        NOT NULL,
    retired_on     DATE
);
