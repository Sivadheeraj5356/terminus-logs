-- meridian database schema: telemetry frames and the station registry.

CREATE SCHEMA telemetry;

CREATE TABLE telemetry.readings (
    reading_id     bigserial PRIMARY KEY,
    channel        text        NOT NULL,
    captured_at    timestamptz NOT NULL,
    sample_rate_hz integer     NOT NULL,
    samples        double precision[] NOT NULL,
    UNIQUE (channel, captured_at)
);

CREATE SCHEMA registry;

CREATE TABLE registry.artifact_review (
    entry_id    integer PRIMARY KEY,
    group_id    text NOT NULL,
    artifact_id text NOT NULL,
    version     text NOT NULL,
    status      text NOT NULL,
    decided_on  date NOT NULL,
    minute_ref  text,
    status_note text NOT NULL
);

CREATE TABLE registry.advisory_register (
    advisory_id text PRIMARY KEY,
    subject     text NOT NULL,
    issued_on   date NOT NULL,
    status      text NOT NULL
);
