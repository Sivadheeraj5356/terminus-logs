# Report schema

`report.json` is UTF-8 JSON with deterministic key order and a trailing newline.

Required top-level fields:

`epochs_seen` is the highest epoch value seen during replay plus one; it is not the count of distinct epoch values. For example, replaying epochs `0` and `20` reports `"epochs_seen": 21`.

```json
{
  "schema_version": 3,
  "epochs_seen": 0,
  "applied_events": 0,
  "cancelled_events": 0,
  "superseded_events": 0,
  "duplicate_raw_events": 0,
  "suppressed_hops": 0,
  "open_link_count": 0,
  "quarantined_count": 0,
  "alarm_breach_total": 0,
  "policy_digest": "",
  "policy_lineage_digest": "",
  "raw_input_digest": "",
  "links": []
}
```

Each link row:

```json
{
  "link_id": "alpha>omega",
  "open": false,
  "quarantined": false,
  "hop_count": 0,
  "sum_ms": 0,
  "max_ms": 0,
  "alarm_breaches": 0,
  "sla_ms": 0,
  "buckets": [0, 0, 0, 0, 0, 0],
  "last_epoch": 0,
  "last_seq": 0
}
```

Sorting:

- `links` sorted ascending by `link_id`.
- Object keys in digest canonicalization sorted recursively.
