# Implement the readiness queue worker at `/app/worker.js`. It drains `/app/queue/

Submission: `d0f2cb8e-6962-458b-a865-43d33b8f0d2e`  
Slug: `implement-the-readiness-queue-worker-at-app-worker-js-it-dra`  
Latest archive: `d0f2cb8e-6962-458b-a865-43d33b8f0d2e_submission_2026-07-13T16_30_46.192Z.zip`  
Revisions in Dropbox: 6

## Task summary

Implement the readiness queue worker at `/app/worker.js`. It drains `/app/queue/pending/`, scores Kubernetes deployment manifests referenced by each envelope, and logs non-deferred work to the local MLflow Tracking API at `http://127.0.0.1:5000`. At startup load the readiness contract, rules, MLflow manifest, and model weights only through `config_paths` in the active contract (each `*_env` key and its default). Do not modify anything under `/app/specs/` or `/app/model/`. Score deployments per the active contract: `inference_model`, `score_rounding`, `binding_resolution_order`, `bindings`, `rules_selection`, `rules_stack_merge`, `binding_merge`, `binding_registry`, `job_overlay`, `feature_normalize_cap`, and `model_container_selector`; resolve `profile_aliases` transitively and apply `binding_merge` at every merge step in `binding_resolution_order`. Drain by priority descending, then `job_id` ascending. Envelopes with `defer: true` move to `/app/queue/done/` without scoring; move every pending envelope JSON into `done/`, leave `pending/` empty, and preserve `/app/queue/pending/.seed/`. Write `/app/output/drain_report.json` using `drain_report.top_level_fields`, `job_fields`, and `summary_fields` with internal `drain_report.verdict_tokens` (not lexicon-mapped strings); apply `verdict_lexicon` only where `lexicon_scope` applies.

Required artifacts include: `/app/worker.js`, `/app/queue/pending/`, `/app/specs/`, `/app/model/`, `/app/queue/done/`, `/app/queue/pending/.seed/`, `/app/output/drain_report.json`.

Author vidhantmatta tagged this **hard** machine-learning task (mlflow, tensorflowjs, nodejs, kubernetes, queue-processing, yaml-parsing).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `d0f2cb8e-6962-458b-a865-43d33b8f0d2e_submission_2026-07-13T16_30_46.192Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
