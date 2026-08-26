Depth-aware streaming predictions from the previous step must be replaced: every block in `/app/artifacts/predictions.json` (`set1`, `set2`, `set3`) must use the fully resolved ancestry from `/app/artifacts/provenance.json`, so keys and values no longer diverge across blocks. With fully resolved key `set1_set2_set3`, scale is `4.0`.

`pipeline --check --output artifacts/` must exit `0` when artifacts are consistent and non-zero when prediction keys disagree with provenance metadata, including both simple and compound stale keys.

Fix generation and validation under `/app` — repairing audit alone is not enough if predictions are still produced from partial ancestry. Rebuild with `cargo build --release --bin pipeline`. The verifier rebuilds from source; static JSON is not accepted.

Signal completion when this step passes verification before advancing — rerun the pipeline and audit mode for this step, not prior work.
