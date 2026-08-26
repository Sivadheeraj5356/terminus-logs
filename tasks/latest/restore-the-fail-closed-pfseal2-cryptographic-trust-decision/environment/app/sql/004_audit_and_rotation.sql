CREATE TABLE pfseal_audit (
    job_id UBIGINT PRIMARY KEY,
    deployment_id VARCHAR NOT NULL,
    image_digest VARCHAR NOT NULL,
    envelope_key_version USMALLINT NOT NULL,
    active_key_version USMALLINT NOT NULL,
    metadata_revision UBIGINT NOT NULL,
    key_attestation_sha256 VARCHAR NOT NULL,
    header_sha256 VARCHAR NOT NULL,
    plaintext_sha256 VARCHAR NOT NULL,
    secret_name VARCHAR NOT NULL,
    rotation_counter UBIGINT NOT NULL,
    rotation_decision VARCHAR NOT NULL CHECK (rotation_decision IN ('current', 'rotate')),
    audit_sequence UBIGINT NOT NULL,
    previous_audit_hash VARCHAR NOT NULL,
    audit_hash VARCHAR NOT NULL,
    worker_id VARCHAR NOT NULL,
    processed_at TIMESTAMP NOT NULL
);

CREATE TABLE pfseal_audit_heads (
    deployment_id VARCHAR PRIMARY KEY,
    last_sequence UBIGINT NOT NULL,
    last_audit_hash VARCHAR NOT NULL
);

CREATE TABLE prefect_secret_state (
    deployment_id VARCHAR NOT NULL,
    secret_name VARCHAR NOT NULL,
    last_rotation_counter UBIGINT NOT NULL,
    last_plaintext_sha256 VARCHAR NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (deployment_id, secret_name)
);

CREATE TABLE pfseal_rotation_outbox (
    job_id UBIGINT PRIMARY KEY,
    deployment_id VARCHAR NOT NULL,
    secret_name VARCHAR NOT NULL,
    from_key_version USMALLINT NOT NULL,
    to_key_version USMALLINT NOT NULL,
    enqueued_at TIMESTAMP NOT NULL
);
