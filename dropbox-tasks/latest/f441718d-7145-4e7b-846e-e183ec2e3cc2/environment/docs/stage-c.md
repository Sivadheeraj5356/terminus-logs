# Stage C — Execution Scheduler & Executor

## Scheduler

- Workers sorted ascending by ID
- Assignment index `i % len(workers)` over plan order
- `max_retries`: node value if > 0 else policy `max_retries` (no off-by-one)
- `timeout_ms`: node value if > 0 else policy `timeout_ms`

## Executor

- Execute nodes in **plan order** (not reversed)
- Mock outputs via `DomainHash("exec-output", ...)`
- Cache key:

```
DomainHash("cache-v1", workflowID + "\n" + nodeID + "\n" + paramsDigest + "\n" + version)
```

- On cache hit: reuse stored result (do not re-execute)
- Journal entries appended in execution order
- Journal hash: `DomainHash("journal-v1", canonical_json({workflow_id, entries}))`
  where `entries` are sorted by ascending `seq` and each wire entry includes only
  `{action, digest, meta, node_id, seq}` (no wall-clock fields)

## Outputs

`state/schedule.json`, `state/execution.json`, `state/journal.json`
