PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deployment_profiles (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cargo_components (
    profile_id TEXT NOT NULL,
    crate_name TEXT NOT NULL,
    version TEXT NOT NULL,
    component_role TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    advisory_id TEXT,
    disabled_reason TEXT,
    PRIMARY KEY (profile_id, crate_name),
    FOREIGN KEY (profile_id) REFERENCES deployment_profiles(profile_id)
);

CREATE TABLE IF NOT EXISTS inference_defaults (
    profile_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    current_value TEXT NOT NULL,
    hardened_value TEXT NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, setting_key),
    FOREIGN KEY (profile_id) REFERENCES deployment_profiles(profile_id)
);

CREATE TABLE IF NOT EXISTS advisory_evidence (
    profile_id TEXT NOT NULL,
    advisory_id TEXT NOT NULL,
    crate_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    package_spec TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    audit_run_id TEXT NOT NULL,
    PRIMARY KEY (profile_id, advisory_id, crate_name),
    FOREIGN KEY (profile_id) REFERENCES deployment_profiles(profile_id)
);

CREATE TABLE IF NOT EXISTS harden_runs (
    run_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    ops_digest TEXT NOT NULL,
    lock_digest TEXT NOT NULL,
    advisory_count INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES deployment_profiles(profile_id)
);
