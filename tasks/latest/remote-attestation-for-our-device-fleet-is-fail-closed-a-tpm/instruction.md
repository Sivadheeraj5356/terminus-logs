Remote attestation for our device fleet is fail-closed: a TPM2 quote cartridge must prove authenticity and measurement integrity before the device may be marked trusted. Reject forged ECDSA P-256 quotes, nonce replays, PCR digests that do not bind the event log, clock or counter rollback, unsafe clocks, disallowed firmware versions, and reference-measurement or event-order policy violations. Accept only evidence that authenticates and also satisfies the published appraisal rules.

Evidence cartridges live under `/app/data`. Normative attestation, encoding, schema, and invocation contracts live under `/app/docs`. TPM 2.0-inspired grounding notes are under `/app/source_snapshots/README.md`.

Appraisal order is chronological by `received_at`, then `request_id`. Trust decisions land in `/app/output/report.json`. Whole-run structural failures exit nonzero with nonempty stderr and leave no partial report; per-request security rejects still exit zero with a complete report. Identical inputs must yield a byte-identical report.

Duplicate identity records are whole-run structural failures, not per-request
security rejections. In particular, duplicate device_id, attestation_key_id,
policy_id, event_log_id, nonce_id, or request_id values must cause a nonzero
exit with nonempty stderr and no report or temporary report sibling.

Each ID must be unique within its own declared identity namespace. This does
not require unrelated ID kinds to use different text values.

The exact conflict_type, subject, reason_code, and related_values projection is
normative in report_schema.md. Do not choose an alternative plausible subject
or omit contextual values.
