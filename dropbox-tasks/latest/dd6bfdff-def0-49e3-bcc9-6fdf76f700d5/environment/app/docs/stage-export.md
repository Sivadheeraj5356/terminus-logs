# Stage export

When BOILOFF_EXPORT_FROM_STAGE_ONLY is true, lng-boiloff-reconciler reads boiloff-stage.json from BOILOFF_STATE_DIR, validates stage_hash and stage_seal, and writes boiloff-report.json and corrective-actions.tsv to BOILOFF_OUTPUT_DIR without reading input CSV or JSON files.

Tampering with staged tank metrics after staging must fail seal validation.

Stage-only export must produce identical report content to a full run when the stage file is unchanged.
