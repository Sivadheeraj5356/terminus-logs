INSERT OR REPLACE INTO meta (key, value) VALUES ('generation', '2025-07');
INSERT OR REPLACE INTO meta (key, value) VALUES ('inventory_source', 'embedserve-production');

INSERT OR REPLACE INTO deployment_profiles (profile_id, name, enabled)
VALUES ('embedserve-default', 'embedserve-default', 1);

INSERT OR REPLACE INTO cargo_components
    (profile_id, crate_name, version, component_role, enabled, advisory_id, disabled_reason)
VALUES
    ('embedserve-default', 'rsa', '0.9.6', 'tokenizer', 1, NULL, NULL),
    ('embedserve-default', 'serde_json', '1.0.150', 'tokenizer', 1, NULL, NULL),
    ('embedserve-default', 'embedserve-tokenizer', '0.1.0', 'tokenizer', 1, NULL, NULL);

INSERT OR REPLACE INTO inference_defaults
    (profile_id, setting_key, current_value, hardened_value, applied)
VALUES
    ('embedserve-default', 'model_sandbox_enabled', 'false', 'true', 0),
    ('embedserve-default', 'allow_local_weight_files', 'true', 'false', 0),
    ('embedserve-default', 'mmap_model_weights', 'true', 'false', 0),
    ('embedserve-default', 'tokenizer_remote_code', 'true', 'false', 0),
    ('embedserve-default', 'tokenizer_trust_remote_code', 'true', 'false', 0);
