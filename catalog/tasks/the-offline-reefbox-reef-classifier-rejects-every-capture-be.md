# The offline ReefBox reef-classifier rejects every capture because its deployment

Submission: `c3861774-5884-4b89-b65d-9eae72836413`  
Slug: `the-offline-reefbox-reef-classifier-rejects-every-capture-be`  
Latest archive: `c3861774-5884-4b89-b65d-9eae72836413_submission_2026-07-03T15_37_35.050Z.zip`  
Revisions in Dropbox: 1

## Task summary

The offline ReefBox reef-classifier rejects every capture because its deployment manifest is missing the per-device calibration embedded *inside* the PNG capture files. The deliverable is a single verified inference manifest at **`/app/out/inference_manifest.json`**, produced by running **`terraform apply`**. The calibration format and every processing rule are undocumented except in the field notebook; this file specifies the deliverable and its output contract, and the notebook defines how each value is computed. The verifier runs `terraform apply` itself and checks the resulting manifest.

Required artifacts include: `/app/out/inference_manifest.json`, `/app/pipeline/build_manifest.sh`.

Author anonymous tagged this **hard** machine-learning task (terraform, jq, yq, png, binary-format, reverse-engineering, long-context, calibration).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `c3861774-5884-4b89-b65d-9eae72836413_submission_2026-07-03T15_37_35.050Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
