# Cursor trace records

`/app/ops/runtime/cursor_trace.jsonl` contains one JSON object per lifecycle event. The `seq` field gives total order. Partition-bearing events have `partition_id`, `cursor_start`, `cursor_end`, `prev_cursor`, and `action`. `action = export` contributes to the exported cursor lineage. `action = omit` records a partition window that was seen by the service but superseded by rollback; it contributes to the omission ledger but not to the exported lineage.

Reload and rollback records have no partition payload. They explain why two partition events may share a cursor start after a service boot change. The final authority is still the ordered partition-bearing cursor events: do not infer the final partition set from file names alone.
