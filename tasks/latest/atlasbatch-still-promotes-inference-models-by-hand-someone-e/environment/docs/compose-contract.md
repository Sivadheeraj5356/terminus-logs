# Compose inference service contract

File: `/app/compose/inference.yml`

## Service name

The promotion CLI reads the **`inference`** service only. Other services in the same compose file (for example shadow deployments) must be ignored even when they carry Atlas labels.

## Required labels

| Label key | Maps to DB column |
|-----------|-------------------|
| `atlas.model_id` | `model_id` |
| `atlas.sklearn_pin` | `sklearn_pin` |
| `atlas.artifact_digest` | `artifact_digest` |

Labels are string values on the `inference` service. Read values from the service `labels` map only — not from `environment` entries.

Digest values include the `sha256:` prefix.

## CLI usage

```
lua /app/bin/atlas-promote run --candidate <id> --compose /app/compose/inference.yml
```

The `--compose` flag may point at an alternate compose file for dry-run comparisons.
