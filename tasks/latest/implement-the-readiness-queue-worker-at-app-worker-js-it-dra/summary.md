# Implement the readiness queue worker at `/app/worker.js`. It drains `/app/queue/

- **UUID:** `d0f2cb8e-6962-458b-a865-43d33b8f0d2e`
- **Slug:** `implement-the-readiness-queue-worker-at-app-worker-js-it-dra`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Implement the readiness queue worker at `/app/worker.js`. It drains `/app/queue/pending/`, scores Kubernetes deployment manifests referenced by each envelope, and logs non-deferred work to the local MLflow Tracking API at `http://127.0.0.1:5000`.

At startup load the readiness contract, rules, MLflow manifest, and model weights only through `config_paths` in the active contract (each `*_env` key and its default). Do not modify anything under `/app/specs/` or `/app/model/`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
