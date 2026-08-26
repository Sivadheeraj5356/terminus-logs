# # Cross-conformal p-values for forest cover-type mapping

Submission: `a0dbbb54-d9e2-47eb-9e91-e8433220be33`  
Slug: `cross-conformal-p-values-for-forest-cover-type-mapping`  
Latest archive: `a0dbbb54-d9e2-47eb-9e91-e8433220be33_submission_2026-07-17T21_30_52.477Z.zip`  
Revisions in Dropbox: 1

## Task summary

A land-survey program classifies terrain cells into seven forest cover types. For a batch of unlabelled evaluation cells you must compute, from fixed nonconformity scores and a K-fold partition of the labelled cells, **cross-conformal p-values** for every candidate cover type, combine them across folds with the requested validity-preserving rule, and assemble label sets — implementing the exact finite-sample procedure below. All graded arithmetic is exact rational arithmetic; every reported number is a reduced fraction. Write a base-R program at `/app/environment/analysis.R`. It reads its input directory from the environment variable `CONFORMAL_DATA_DIR` (default `/app/environment/data`) and writes outputs to `CONFORMAL_OUT_DIR` (default `/app/environment/outputs`). It runs on several input directories with the same schema but different data (different fold counts included), so implement the procedure in general. Do not fit any model; the scores are fixed inputs. Key requirements: **Per-fold smoothed p-value.** With `g = #{i in S_k : s_i > s}` and; **Combination.** Over the `K` per-fold p-values, by the request's rule:; **Label set.** At the request's level `alpha = alpha_num / alpha_den`, the; **Diagnostics.** For every combination of `wilderness_area`, level, and.

Required artifacts include: `/app/environment/analysis.R`, `/app/environment/data`, `/app/environment/outputs`.

Author anonymous tagged this **medium** machine-learning task (conformal-prediction, cross-conformal, p-values, finite-sample, exact-arithmetic).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a0dbbb54-d9e2-47eb-9e91-e8433220be33_submission_2026-07-17T21_30_52.477Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
