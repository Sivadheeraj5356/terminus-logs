# The 2027Q1 challenger models are stuck in the promotion queue: none of them can 

Submission: `dfa250ff-9b41-4ed4-94cf-efddb000d7c5`  
Slug: `the-2027q1-challenger-models-are-stuck-in-the-promotion-queu`  
Latest archive: `dfa250ff-9b41-4ed4-94cf-efddb000d7c5_submission_2026-07-17T15_24_53.368Z.zip`  
Revisions in Dropbox: 1

## Task summary

The 2027Q1 challenger models are stuck in the promotion queue: none of them can be scored for feature drift right now, so nothing is promoted to champion this cycle and the incumbents keep serving. I need you to add that drift-screening step to the model registry as its V7 migration. The reference data — this quarter's runs, the monitored feature catalog, the cohort register — already lives in the registry at /app/data/registry, and the stability scores the feature-audit pipeline produced, together with each run's audit lifecycle events, sit in the sealed bundle at /app/archive/fa_2027q1 behind its manifest. V7 has two jobs: ingest the bundle into a `feature_audit` table, and from the eligible observations write one row per audited run into `promotion_audit`, each ending in a PROMOTE, HOLD or REJECT determination. What counts as an observation, what drift means for each feature family, how the dated amendments apply, and how a run lands on its determination are the business logic in the 2027Q1 review dossier at /app/docs/model_review_dossier.md. Read it closely: it is long, it is a governance document, and it contradicts itself, because much of it is history rather than the criteria in force — where the narrative and the amendment log disagree, the amendment log governs.

Required artifacts include: `/app/data/registry`, `/app/archive/fa_2027q1`, `/app/docs/model_review_dossier.md`, `/app/out/promotion_audit.csv`.

Author anonymous tagged this **medium** machine-learning task (mlops, model-evaluation, model-registry, feature-drift, requirements-extraction, h2-database).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `dfa250ff-9b41-4ed4-94cf-efddb000d7c5_submission_2026-07-17T15_24_53.368Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
