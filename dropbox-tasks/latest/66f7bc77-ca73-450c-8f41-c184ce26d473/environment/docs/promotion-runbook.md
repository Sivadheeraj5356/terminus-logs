# AtlasBatch model promotion runbook

Promotion decisions gate production rollout of inference models. The Lua CLI at `/app/bin/atlas-promote` automates the checks below.

## Inputs

| Source | Path |
|--------|------|
| Evaluation database | `/app/data/eval.db` |
| Compose service | `/app/compose/inference.yml` (service name `inference`) |
| Canary fixture | Path from `candidates.canary_fixture` column |
| Upstream sklearn tags | Mirror at `/app/config/upstream.toml` → `mirror_path` |
| Evaluation clock | `/app/config/eval-clock.toml` → `as_of_date` |
| Policy comms | `/app/archives/comms/` |
| Artifact manifests | `/app/registry/manifests/` per `/app/docs/artifact-manifest.md` |

Conflicting guidance may appear in `/app/archives/engineering/` — ratified comms and `/app/docs/` take precedence.

## Gate rules

A candidate is **rejected** when any gate fails. Record every failure in `reasons` using the codes defined in `/app/docs/promotion-decision.schema.json`.

### Upstream tag

The candidate `sklearn_pin` must exist as a release tag in the upstream mirror. See `/app/docs/upstream-mirror.md`.

### Metric regression

Compare candidate metrics from the database against the canary baseline in the fixture JSON. See `/app/docs/eval-db-schema.md` for rounding rules.

### Latency breach

Candidate `latency_p99_ms` must not exceed the effective ceiling. Default ceiling is **45 ms**. Batch-specific waivers may override the default — see `/app/archives/comms/` and the evaluation clock.

### Compose metadata mismatch

The `inference` service labels must match the candidate row. See `/app/docs/compose-contract.md`.

### Canary batch mismatch

The fixture `batch_id` must match the candidate `batch_id` column.

### Evaluation stale

The holdout evaluation date must fall within the active window. See `/app/archives/comms/eval-window-policy.md`.

### Holdout sample minimum

The candidate `holdout_samples` count must meet the database threshold in `/app/docs/eval-db-schema.md`.

### Artifact manifest

The candidate `sklearn_pin` and `artifact_digest` must match a `[[release]]` row in `/app/registry/manifests/<model_id>.toml`. See `/app/docs/artifact-manifest.md`.

## Output

Write `/app/output/promotion-decision.json` per `/app/docs/promotion-decision.schema.json`.

When all gates pass: `approved` is `true`, `status` is `"approved"`, `reasons` is empty.

When any gate fails: `approved` is `false`, `status` is `"rejected"`, `reasons` lists every failed gate code sorted alphabetically.

## Determinism

JSON keys are sorted alphabetically at every object level.
