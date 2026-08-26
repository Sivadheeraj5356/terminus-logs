The pipeline under `/app` ingests batch JSON from `/app/data/` (`set1.json`, `set2.json`, `set3.json`) and writes `/app/artifacts/provenance.json` (`chains` with `group_id`, `history`, `key`) and `/app/artifacts/predictions.json` (records under `set1`, `set2`, `set3` with `probe_id`, `value`, `key`).

After all batches, each group's `history` must contain every source tag seen, stored in sorted tag order (for example `["set1","set2","set3"]`), and `key` must be the sorted underscore-joined form of that set. With only `set1.json` present, `history` is `["set1"]` and `key` is `set1`. The `set1` prediction block must use single-source ancestry: `key` is `set1` and `value` uses scale `1.0` (`value = dot(probe_vector, weights) * scale`). See `/app/docs/data_spec.md`.

Fix the source under `/app`. Rebuild with `cargo build --release --bin pipeline` before local checks. The verifier rebuilds from source; static JSON is not accepted.

Signal completion when this step passes verification before advancing — do not rely on stale terminal output from earlier work.
