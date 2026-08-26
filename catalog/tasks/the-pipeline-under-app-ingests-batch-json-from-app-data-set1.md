# The pipeline under `/app` ingests batch JSON from `/app/data/` (`set1.json`, `se

Submission: `9383109f-ae02-400d-ae09-30dfd25678ac`  
Slug: `the-pipeline-under-app-ingests-batch-json-from-app-data-set1`  
Latest archive: `9383109f-ae02-400d-ae09-30dfd25678ac_submission_2026-07-09T11_58_31.786Z.zip`  
Revisions in Dropbox: 1

## Task summary

The pipeline under `/app` ingests batch JSON from `/app/data/` (`set1.json`, `set2.json`, `set3.json`) and writes `/app/artifacts/provenance.json` (`chains` with `group_id`, `history`, `key`) and `/app/artifacts/predictions.json` (records under `set1`, `set2`, `set3` with `probe_id`, `value`, `key`). After all batches, each group's `history` must contain every source tag seen, stored in sorted tag order (for example `["set1","set2","set3"]`), and `key` must be the sorted underscore-joined form of that set. With only `set1.json` present, `history` is `["set1"]` and `key` is `set1`. The `set1` prediction block must use single-source ancestry: `key` is `set1` and `value` uses scale `1.0` (`value = dot(probe_vector, weights) * scale`). See `/app/docs/data_spec.md`.

Required artifacts include: `/app/data/`, `/app/artifacts/provenance.json`, `/app/artifacts/predictions.json`, `/app/docs/data_spec.md`.

Author anonymous tagged this **hard** machine-learning task (rust, ml-pipelines, provenance, adversarial-generalization, cross-artifact-invariants).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `9383109f-ae02-400d-ae09-30dfd25678ac_submission_2026-07-09T11_58_31.786Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
