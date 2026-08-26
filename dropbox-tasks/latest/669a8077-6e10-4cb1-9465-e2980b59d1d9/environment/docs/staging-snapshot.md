# Staging snapshot schema

/app/state/batch-release-snapshot.json is a compact single-line JSON object with schema_version 1, batch_id, generated_at, metadata_digest, and gate_results.

gate_results is sorted by gate name ascending. Each gate row contains gate, passed, and blockers. gate is one of documentation, environmental, equipment, or qc. blockers is a sorted unique array of exact blocker strings from the policy docs.

generated_at equals batch_policy.json generated_at. metadata_digest follows /app/docs/metadata-contract.md.

attest-release must write this snapshot before the trust attestation is issued. The attestation must load gate_results from the stage path on disk rather than deriving them only from in-memory dossier state.
