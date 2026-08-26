# Stage G — State Verification

## Checks

- **Lineage**: for each node, plan parents (`edges where to=node`) equal `depends_on`
- **Graph**: directed edge presence for every dependency; plan order covers every node
- **Checkpoint**: `VerifyIntegrity` on recovered checkpoint
- **Replay**: `replay.Compare(execution, replay)`
- **Hash**: recovered checkpoint `journal_hash` equals execution `journal_hash`

Verification hash: `DomainHash("verification-v1", canonical report fields)`.

## Outputs

`state/verification.json`, `output/verification.json`
