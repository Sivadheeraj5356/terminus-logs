CREATE TABLE pfseal_transparency_checkpoints (
    checkpoint_sequence UBIGINT PRIMARY KEY,
    job_id UBIGINT NOT NULL UNIQUE,
    head_count UBIGINT NOT NULL,
    merkle_root VARCHAR NOT NULL,
    triggering_audit_hash VARCHAR NOT NULL,
    previous_checkpoint_hash VARCHAR NOT NULL,
    previous_event_mmr_root VARCHAR NOT NULL,
    event_mmr_root VARCHAR NOT NULL,
    frontier_json VARCHAR NOT NULL,
    frontier_sha256 VARCHAR NOT NULL,
    checkpoint_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
