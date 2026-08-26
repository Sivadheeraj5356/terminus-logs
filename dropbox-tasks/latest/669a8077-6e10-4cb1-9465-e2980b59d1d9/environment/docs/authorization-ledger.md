# Authorization evaluation ledger

/app/state/release-auth-ledger.json records attest-release runs for GMP audit continuity. The file is compact single-line JSON with schema_version 1, last_batch_id, last_digest, and evaluation_seq.

When the ledger file is missing, treat evaluation_seq as starting at 0 before the first successful attest-release. Each successful attest-release that writes both the staging snapshot and the audit report must set last_batch_id to the lot batch_id, set last_digest to that run metadata_digest, and set evaluation_seq to the previous evaluation_seq plus one.

The audit report evaluation_seq field must equal the ledger evaluation_seq after the bump for that run. Re-running attest-release on unchanged metadata still advances evaluation_seq.
