# Lot-release integrity trust attestation schema

/app/output/batch-release-audit.json is a compact single-line JSON object with schema_version 1, batch_id, release_ready, status, gate_results, summary, metadata_digest, staging_seal, and evaluation_seq.

release_ready is true only when every gate_results row has passed true. status is released when release_ready is true and hold otherwise. Do not use alternate labels such as ready or blocked.

gate_results must be taken from the on-disk staging snapshot for the same attest-release run after that snapshot has been written. summary contains gates_passed, gates_failed, qc_tests_required, qc_tests_approved, equipment_units counting used_in_batch rows, equipment_released counting used rows with status released, environmental_excursions_open counting environmental gate blockers, documentation_required, and documentation_approved counting approved documentation rows.

metadata_digest must equal the staging snapshot digest. staging_seal is the FNV-1a 64-bit seal of the exact on-disk staging snapshot file bytes including the trailing newline, rendered as batch-fnv64- followed by sixteen lowercase hex digits. evaluation_seq is the evaluation_seq value from /app/state/release-auth-ledger.json after that ledger is advanced for the run. JSON serialization must be compact with no pretty printing and a single trailing newline.
