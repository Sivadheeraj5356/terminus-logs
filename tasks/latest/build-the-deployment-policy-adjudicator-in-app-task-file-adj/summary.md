# Build the deployment policy adjudicator in `/app/task_file/adjudicate.js`. It mu

- **UUID:** `3e9e18d5-329f-49ca-887c-6872889729cc`
- **Slug:** `build-the-deployment-policy-adjudicator-in-app-task-file-adj`
- **Category:** security
- **Difficulty:** medium

## Summary

Build the deployment policy adjudicator in `/app/task_file/adjudicate.js`. It must run as `node /app/task_file/adjudicate.js /app/task_file/input_data /app/task_file/output_data`, read `policy.json`, `runtime_state.json`, `test_runs.json`, `exceptions.json`, and `candidates.json` from the input directory, and write `/app/task_file/output_data/deployment_decisions.json` within 20 seconds.

Use `/app/task_file/docs/spec.md` as the engineering contract for the required JSON schema, field meanings, eligibility rules, warning and rejection semantics, selection constraints, sorting, tie-breaks, and summary fields. The output top-level fields are exactly `selected`, `deferred`, `rejected`, and `summary`; row fields and summary fields are listed in the contract.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
