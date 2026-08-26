# Field overview

Common workload entries carry `manifest_id`, `name`, `namespace`, `labels`, and optional `annotations`.

For unit_tag material the overview covers label keys only. Sort label keys lexicographically and emit `key=value` tokens for the north band profile (`p7`).

The north band profile keeps annex_keys off. Only labels participate in ordering for that band before the revision token is attached.

Historical note: an older probe path CRC32-hashed the label map alone, used letter `N` for every band, hashed the whole journal file for tips, and ignored seal windows. That path is not the graded matrix reduction.

## Matrix driver

Rebuild with `/app/environment/scripts/bake_ws.sh`, then run:

```
/app/environment/build/spw_run --matrix /app/environment/fixtures/q2_sets --out /app/output/feasibility_certificate.json
```

Each row binds `manifest_id`, `canonical_byte_digest`, `unit_tag`, `scope_band`, `cache_epoch`, `journal_tip_hex`, and `seal_window`.

The driver is snapshot-aware. Running the same matrix/profile/slice content
again restores the committed certificate without appending journals or bumping
cache epochs. A content change is a new snapshot and continues the existing
lineage. Changed snapshots run under a recoverable stage transaction so partial
rows cannot become durable lineage. The exact identity, failure-injection, and
rollback rules are in `docs/stage_rules.md`.
