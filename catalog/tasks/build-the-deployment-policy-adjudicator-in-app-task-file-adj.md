# Build the deployment policy adjudicator in `/app/task_file/adjudicate.js`. It mu

Submission: `3e9e18d5-329f-49ca-887c-6872889729cc`  
Slug: `build-the-deployment-policy-adjudicator-in-app-task-file-adj`  
Latest archive: `3e9e18d5-329f-49ca-887c-6872889729cc_submission_2026-07-10T07_36_14.278Z.zip`  
Revisions in Dropbox: 1

## Task summary

Build the deployment policy adjudicator in `/app/task_file/adjudicate.js`. It must run as `node /app/task_file/adjudicate.js /app/task_file/input_data /app/task_file/output_data`, read `policy.json`, `runtime_state.json`, `test_runs.json`, `exceptions.json`, and `candidates.json` from the input directory, and write `/app/task_file/output_data/deployment_decisions.json` within 20 seconds. Use `/app/task_file/docs/spec.md` as the engineering contract for the required JSON schema, field meanings, eligibility rules, warning and rejection semantics, selection constraints, sorting, tie-breaks, and summary fields. The output top-level fields are exactly `selected`, `deferred`, `rejected`, and `summary`; row fields and summary fields are listed in the contract.

Required artifacts include: `/app/task_file/adjudicate.js`, `/app/task_file/input_data`, `/app/task_file/output_data`, `/app/task_file/output_data/deployment_decisions.json`, `/app/task_file/docs/spec.md`.

Author Anonymous tagged this **medium** security task (security, nodejs, policy-engine, deployment, attestation).

Time estimates: expert ~150 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `3e9e18d5-329f-49ca-887c-6872889729cc_submission_2026-07-10T07_36_14.278Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
