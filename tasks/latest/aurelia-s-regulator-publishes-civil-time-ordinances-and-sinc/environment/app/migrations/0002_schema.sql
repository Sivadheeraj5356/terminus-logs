CREATE TABLE IF NOT EXISTS zones (
    zone              TEXT PRIMARY KEY,
    meridian_seconds  INTEGER NOT NULL,
    tzif_sha256       TEXT    NOT NULL,
    transition_count  INTEGER NOT NULL,
    first_transition  BIGINT  NOT NULL,
    last_transition   BIGINT  NOT NULL,
    posix_footer      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ordinances (
    zone             TEXT    NOT NULL REFERENCES zones(zone) ON DELETE CASCADE,
    ordinance        TEXT    NOT NULL,
    kind             TEXT    NOT NULL CHECK (kind IN ('establish', 'repeal')),
    enacted          DATE    NOT NULL,
    enactment_seq    INTEGER NOT NULL,
    effective_epoch  BIGINT  NOT NULL,
    effective_anchor TEXT    NOT NULL CHECK (effective_anchor IN ('wall','standard','universal')),
    standard_offset  INTEGER,
    basis            TEXT,
    repeals          TEXT,
    PRIMARY KEY (zone, ordinance)
);

CREATE TABLE IF NOT EXISTS transitions (
    zone          TEXT     NOT NULL REFERENCES zones(zone) ON DELETE CASCADE,
    at_epoch      BIGINT   NOT NULL,
    utoff_before  INTEGER  NOT NULL,
    utoff_after   INTEGER  NOT NULL,
    isdst_after   SMALLINT NOT NULL CHECK (isdst_after IN (0, 1)),
    abbrev_after  TEXT     NOT NULL,
    ordinance     TEXT     NOT NULL,
    PRIMARY KEY (zone, at_epoch)
);

-- One row per governing-ordinance interval. Two ordinances cannot govern the same
-- instant, so the engine refuses a timeline whose precedence windows overlap.
CREATE TABLE IF NOT EXISTS segments (
    zone            TEXT      NOT NULL REFERENCES zones(zone) ON DELETE CASCADE,
    valid           TSTZRANGE NOT NULL,
    ordinance       TEXT      NOT NULL,
    standard_offset INTEGER   NOT NULL,
    CONSTRAINT segments_no_overlap EXCLUDE USING gist (zone WITH =, valid WITH &&)
);
