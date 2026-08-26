# Checkpoint and resume

Checkpoint snapshots are JSON files under `checkpoint_dir/TAG.snap` with:

- `schema_version`, `epoch`, `next_seq`, `applied_events`, `audit_counts`
- `policy_state`, `policy_lineage_digest`, `links`, `winner_keys`, `line_cursors`, `raw_input_digest`

Rules:

- `checkpoint` saves complete state after the checkpoint event is selected and applied.
- `winner_keys` contains all selected identity keys, including cancelled winners.
- `line_cursors` is per lane and stores the last consumed line number.
- On `--resume-tag`, restore all state and continue without reapplying prior selected records.
- Resume must reject any event with `epoch < snapshot.epoch`.
- Resume must reject an event in the checkpoint epoch when it appears before the saved lane cursor but is absent from `winner_keys`.
- Resume output must be byte-identical to uninterrupted output for report, digest, and audit.
