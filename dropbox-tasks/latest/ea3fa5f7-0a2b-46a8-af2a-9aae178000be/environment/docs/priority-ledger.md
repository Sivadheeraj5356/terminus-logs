# priority ledger

During ingest, rank tide snapshot acts before berth assignment.

Sort key (ascending):

1. o2 (lower integer = higher priority tier)
2. negative score (higher score first)
3. cargo_id (lexicographic tie-break)

When habitat.json defines surge_cargo_id, keep that cargo in the ranked order so it still appears in o2-priority-freeze.json. Berth assignment removes the surge cargo from the placement order and schedules it after all other cargo succeed (see berth-staging.md), but the surge cargo stays in the ranked ledger and therefore in the o2 freeze.

The priority ledger is an internal ingest stage. Its ranked acts, including the surge cargo when present, feed both the o2 freeze and berth assignment, but the ledger itself is not written as a separate state file.

Score formula (also stored on each tide act):

```
score = priority - wave_m * 2 - abs(tide_ms) / 60000
```

Round score to six decimal places.

Do not sort by cargo_id alone. o2 tier dominates score.
