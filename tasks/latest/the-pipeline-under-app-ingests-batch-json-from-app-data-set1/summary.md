# The pipeline under `/app` ingests batch JSON from `/app/data/` (`set1.json`, `se

- **UUID:** `9383109f-ae02-400d-ae09-30dfd25678ac`
- **Slug:** `the-pipeline-under-app-ingests-batch-json-from-app-data-set1`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The pipeline under `/app` ingests batch JSON from `/app/data/` (`set1.json`, `set2.json`, `set3.json`) and writes `/app/artifacts/provenance.json` (`chains` with `group_id`, `history`, `key`) and `/app/artifacts/predictions.json` (records under `set1`, `set2`, `set3` with `probe_id`, `value`, `key`). After all batches, each group's `history` must contain every source tag seen, stored in sorted tag order (for example `["set1","set2","set3"]`), and `key` must be the sorted underscore-joined form of that set.

With only `set1.json` present, `history` is `["set1"]` and `key` is `set1`. The `set1` prediction block must use single-source ancestry: `key` is `set1` and `value` uses scale `1.0` (`value = dot(probe_vector, weights) * scale`).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
