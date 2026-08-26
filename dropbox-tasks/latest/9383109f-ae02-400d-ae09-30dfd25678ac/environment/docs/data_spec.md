# Batch and artifact contract

## Inputs

Batch state files live under `/app/data/` as `setN.json` with companion `valsN.csv` feature tables. Each batch row names a `group_id`, `source` tag, timestamp, and numeric `values` vector.

The pipeline discovers `set*.json` files, sorts them by filename, and ingests each file as one batch. Source tags inside the JSON (not the filename) define ancestry.

## Outputs

- `/app/artifacts/provenance.json` — `chains[]` with `group_id`, `history` (source tags), and derived `key`
- `/app/artifacts/predictions.json` — per batch-state blocks (`set1`, `set2`, `set3`) of `{probe_id, value, key}` records

## Probe profiles (fixed for this pipeline)

| Probe | Feature vector |
|-------|----------------|
| 1 | 1.0, 2.0, 3.0 |
| 2 | 1.5, 2.5, 3.5 |

Default per-feature weight is `1.0` unless `target/weights.json` overrides it after training.

## Ancestry keys

A group's `key` is the sorted, deduplicated batch `source` tags joined with underscores. The same tag set must produce the same `key` and the same sorted `history` regardless of ingestion order.

## Streaming vs fully resolved predictions

While batches are still being applied, a prediction `key` at a given state block reflects only sources accumulated through that batch depth, and `value` uses the scale for that partial key. After all batches are applied, provenance records the fully resolved ancestry. Downstream consumers that require identical predictions across every state block must use that fully resolved ancestry for every block.

## Prediction values

`value = dot(probe_vector, weights) * scale(ancestry_key)` where `scale` is defined by `key_to_scale` in the inference module:

| ancestry key | scale |
|--------------|-------|
| `set1` | 1.0 |
| `set1_set2` | 2.0 |
| `set1_set2_set3` | 4.0 |
| anything else | 1.0 |

## Audit mode

The pipeline binary accepts `--check --output <dir>` to validate existing artifacts without re-ingesting. It must exit with a non-zero status when any prediction `key` disagrees with the provenance metadata for that probe's group. Both simple tokens and compound (underscore-containing) keys must be checked.
