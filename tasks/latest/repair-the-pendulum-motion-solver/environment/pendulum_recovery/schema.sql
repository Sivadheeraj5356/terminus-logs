-- pendulum_captures.duckdb schema
--
-- This file is both documentation and runnable DDL for the two INPUT tables the
-- generator seeds (jobs, frame_strips). The three OUTPUT tables
-- (recovered_series, fit_results, recovery_edges) are produced by the recovery
-- worker at run time; their contract is documented here as commented DDL so the
-- worker and the read-only report tool agree on column names and types.
--
-- Ground-truth oscillation parameters (natural frequency, decay constant,
-- amplitude) are intentionally absent from every table below: they exist only in
-- the frame-synthesis source and are recovered from the decoded PNG frames.

-- =====================================================================
-- INPUT TABLES (seeded by seed_db.py)
-- =====================================================================

-- Recovery job queue. One row per capture awaiting reconstruction.
CREATE TABLE IF NOT EXISTS jobs (
    job_id        INTEGER PRIMARY KEY,   -- stable job identifier (1..N)
    label         VARCHAR NOT NULL,      -- human-readable capture label
    frames_total  INTEGER NOT NULL,      -- number of frames in this job's strip
    frame_width   INTEGER NOT NULL,      -- width in pixels of a single frame cell
    frame_height  INTEGER NOT NULL,      -- height in pixels of a single frame cell
    status        VARCHAR NOT NULL       -- pending | claimed | done
);

-- One PNG frame-strip BLOB per job. The BLOB decodes to a horizontal montage of
-- frames_total frames laid left-to-right; each frame cell is frame_width wide.
CREATE TABLE IF NOT EXISTS frame_strips (
    job_id     INTEGER PRIMARY KEY,      -- FK to jobs.job_id
    png_blob   BLOB NOT NULL,            -- horizontal frame-strip montage, PNG-encoded
    byte_size  INTEGER NOT NULL          -- length of png_blob in bytes (sanity/manifest)
);

-- =====================================================================
-- OUTPUT TABLES (produced by the recovery worker; documented contract only)
--
-- The report tool reads exactly these columns. The driver creates these
-- tables with at least these columns and types. Extra columns are permitted but
-- ignored by the report tool.
-- =====================================================================

-- Reconstructed angle/displacement time series per job. One row per accepted
-- frame (rejected frames are omitted).
-- CREATE TABLE recovered_series (
--     job_id       INTEGER NOT NULL,   -- FK to jobs.job_id
--     frame_index  INTEGER NOT NULL,   -- 0-based index of the accepted frame
--     t_seconds    DOUBLE  NOT NULL,   -- capture time of the frame
--     angle        DOUBLE  NOT NULL    -- recovered bob displacement / angle
-- );

-- Estimated damped-oscillation fit per job.
-- CREATE TABLE fit_results (
--     job_id             INTEGER PRIMARY KEY,  -- FK to jobs.job_id
--     frequency_hz       DOUBLE NOT NULL,      -- recovered natural frequency
--     decay_per_second   DOUBLE NOT NULL,      -- recovered decay/damping constant
--     rejected_frames    INTEGER NOT NULL      -- count of frames the tracker rejected
-- );

-- Per-frame accepted/rejected audit records feeding the Graphviz recovery DAG.
-- EXACTLY ONE ROW PER FRAME (not grouped segments): every frame in a job's strip
-- contributes one row, tagged 'accepted' or 'rejected'. Each row is one node in
-- the DAG for a job, so the per-job COUNT(kind='rejected') equals that job's
-- rejected-frame count and the total row count equals the DAG node count. The
-- worker also emits a recovery_graph.dot / .svg rendered from these rows.
-- CREATE TABLE recovery_edges (
--     job_id        INTEGER NOT NULL,   -- FK to jobs.job_id
--     node_id       VARCHAR NOT NULL,   -- unique node label within the job's DAG
--     kind          VARCHAR NOT NULL,   -- 'accepted' | 'rejected'
--     frame_index   INTEGER NOT NULL    -- 0-based index of the single frame this row audits
-- );
