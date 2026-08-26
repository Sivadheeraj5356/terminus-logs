Provenance and streaming predictions are still wrong under reordered ingestion. `/app/artifacts/provenance.json` must store `history` in sorted tag order (not insertion order) and a stable `key` for a given tag set regardless of batch-file order. Source payloads may be placed under the `set1`/`set2`/`set3` filenames in any permutation; results must match the canonical-order run.

`/app/artifacts/predictions.json` must contain exactly two probes per `set1`, `set2`, and `set3` block. Each block's `key` and `value` must follow ancestry accumulated only through that batch depth — not one final key on every block. Per-block contracts (`value = dot(probe_vector, weights) * scale`):

| block | ancestry key | scale |
|-------|--------------|-------|
| `set1` | `set1` | 1.0 |
| `set2` | `set1_set2` | 2.0 |
| `set3` | `set1_set2_set3` | 4.0 |

Fix the source under `/app`, rebuild with `cargo build --release --bin pipeline`, and verify locally. The verifier rebuilds from source; static JSON is not accepted.

Signal completion when this step passes verification before advancing.
