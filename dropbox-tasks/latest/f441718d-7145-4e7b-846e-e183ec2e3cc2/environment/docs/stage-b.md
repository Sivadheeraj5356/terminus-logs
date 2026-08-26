# Stage B — DAG Compiler

## Responsibilities

- Build dependency graph from workflow edges (`From` precedes `To`)
- Reject self-loops and cycles
- Topological order with lexicographically **smallest** ready node first
- Include **all** workflow nodes in `order` (including orphans)
- Plan digest:

```
DomainHash("plan-v1", canonical_json({workflow_id, order, edges}))
```

## Outputs

`state/compiled.json`
