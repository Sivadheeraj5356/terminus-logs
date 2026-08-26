# Stage E — Failure Recovery

## Responsibilities

- Resume from `Latest` checkpoint (highest version)
- Retry failed nodes and any not-yet-completed plan nodes
- Rollback/resume must consider **all** workflow nodes (including orphans)
- Recovery digest:

```
DomainHash("recovery-v1", canonical_json({workflow_id, checkpoint_id, resumed, rolled_back, final_status}))
```

## Outputs

`state/recovery.json`, `state/recovered_checkpoint.json`
