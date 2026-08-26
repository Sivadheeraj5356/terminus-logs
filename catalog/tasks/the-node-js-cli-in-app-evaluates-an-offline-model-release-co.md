# The Node.js CLI in `/app` evaluates an offline model-release cohort ledger. Comp

Submission: `1b17e5ed-99fd-44e3-bd00-aa45a5c1d61d`  
Slug: `the-node-js-cli-in-app-evaluates-an-offline-model-release-co`  
Latest archive: `1b17e5ed-99fd-44e3-bd00-aa45a5c1d61d_submission_2026-07-09T04_46_25.796Z.zip`  
Revisions in Dropbox: 4

## Task summary

The Node.js CLI in `/app` evaluates an offline model-release cohort ledger. Complete `/app/src/release.js`, keeping `/app/bin/model-release.js <input-json>` as the command interface, so it reads one JSON document from the input path, resolves each query against the applicable release snapshot, and prints deterministic model assignments as JSON to stdout. Treat `/app/MODEL_RELEASE_CONTRACT.md` as the binding public reference. It defines the input schema, subject canonicalization, release snapshot selection, prerequisite behavior, variant selection hierarchy, output fields, source strings, blocked states, and edge cases. Keep the existing command invocation stable and implement the behavior described by that contract.

Required artifacts include: `/app/src/release.js`, `/app/bin/model-release.js`, `/app/MODEL_RELEASE_CONTRACT.md`.

Author anonymous tagged this **hard** machine-learning task (model-release, cohorts, rollout, offline-evaluation).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `1b17e5ed-99fd-44e3-bd00-aa45a5c1d61d_submission_2026-07-09T04_46_25.796Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
