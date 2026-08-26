CREATE TABLE pfseal_key_witnesses (
    deployment_id VARCHAR NOT NULL,
    witness_id VARCHAR NOT NULL,
    public_key_spki_b64 VARCHAR NOT NULL,
    valid_from_revision UBIGINT NOT NULL,
    valid_through_revision UBIGINT NOT NULL,
    revoked_at_revision UBIGINT,
    PRIMARY KEY (deployment_id, witness_id)
);
