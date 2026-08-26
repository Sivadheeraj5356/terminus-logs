# A TypeScript program in `/app` fits an isotonic regression to a set of scattered

Submission: `19a22c8e-f990-4380-ae3c-378333f26e4f`  
Slug: `a-typescript-program-in-app-fits-an-isotonic-regression-to-a`  
Latest archive: `19a22c8e-f990-4380-ae3c-378333f26e4f_submission_2026-07-20T01_57_27.678Z.zip`  
Revisions in Dropbox: 4

## Task summary

A TypeScript program in `/app` fits an isotonic regression to a set of scattered points and predicts the fitted response at a list of query positions. It must reproduce `sklearn.isotonic.IsotonicRegression` exactly. It reads one JSON object from standard input of the form `{"inputs": [ ... ]}` and writes one JSON object to standard output of the form `{"results": [ ... ]}`, one `{"pred": [ ... ]}` per input in the same order, each holding one predicted value per query. Each input gives the training predictors `x`, the matching responses `y`, an optional per-sample `weight` array (or `null` for unit weights), a boolean `increasing`, and the list of `queries` at which to predict. The `x` values are not guaranteed to be sorted and may contain repeats. The `increasing` flag selects the direction of the fitted monotone trend: when it is `true` the fit is constrained to be non-decreasing, and when it is `false` it is constrained to be non-increasing. The `weight` array, when present, gives each training sample its influence on the fit exactly as `sample_weight` does for the reference estimator. The `out_of_bounds` behaviour of the reference is fixed to `"clip"` for this task, so queries are treated the way that estimator treats them under that setting.

Required artifacts include: `/app/src/main.ts`, `/app/src/isotonic.ts`.

Author anonymous tagged this **hard** machine-learning task (isotonic-regression, monotonic, pava, scikit-learn).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `19a22c8e-f990-4380-ae3c-378333f26e4f_submission_2026-07-20T01_57_27.678Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
