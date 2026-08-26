CREATE TABLE prefect_deployments (
    deployment_id VARCHAR PRIMARY KEY,
    active_key_version USMALLINT NOT NULL,
    minimum_readable_key_version USMALLINT NOT NULL,
    valid_from_revision UBIGINT NOT NULL,
    valid_through_revision UBIGINT NOT NULL
);

CREATE TABLE prefect_deployment_metadata (
    deployment_id VARCHAR NOT NULL,
    revision UBIGINT NOT NULL,
    metadata_key VARCHAR NOT NULL,
    metadata_value VARCHAR NOT NULL,
    PRIMARY KEY (deployment_id, revision, metadata_key)
);
