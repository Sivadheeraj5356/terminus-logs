CREATE TABLE prefect_secret_jobs (
    job_id UBIGINT PRIMARY KEY,
    deployment_id VARCHAR NOT NULL,
    image_digest VARCHAR NOT NULL,
    metadata_revision UBIGINT NOT NULL,
    requested_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('pending', 'processing', 'succeeded', 'failed')),
    attempt_count UINTEGER NOT NULL DEFAULT 0,
    lease_owner VARCHAR,
    lease_until TIMESTAMP,
    completed_at TIMESTAMP,
    failure_code VARCHAR
);
