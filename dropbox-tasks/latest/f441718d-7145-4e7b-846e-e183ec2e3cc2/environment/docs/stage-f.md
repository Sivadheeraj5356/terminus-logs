# Stage F — Deterministic Replay

## Responsibilities

- Rebuild events from journal in ascending `seq`
- Timestamps are epoch-relative RFC3339 **second** precision from journal wall times
  (never wall-clock `time.Now`)
- Replay hash:

```
DomainHash("replay-v1", canonical_json({workflow_id, events}))
```

- `matches_execution` when event digests match execution node digests

## Outputs

`state/replay.json`, `output/replay.json`
