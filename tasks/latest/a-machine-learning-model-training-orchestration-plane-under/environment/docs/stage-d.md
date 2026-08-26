# Stage D — Checkpoint Manager

## Responsibilities

- Persist versioned checkpoints under `state/checkpoints/`
- `Latest(workflow)` returns **highest** version
- Incremental merge:
  - union of `completed`
  - overlay `node_digests` (base then inc)
  - merge metadata (base then inc)
- Snapshot hash: `DomainHash("checkpoint-snap", canonical payload without snapshot_hash field)`

## Outputs

`state/checkpoints.json`, files in `state/checkpoints/`
