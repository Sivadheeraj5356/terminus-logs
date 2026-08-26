# Validation stamp contract

Path: /app/state/validation-stamp.json

| Field | Type | Rule |
|-------|------|------|
| schema | string | reelseal.stamp/v1 |
| manifest_digest | string | sha256 of encryption-manifest.json raw bytes |
| accepted | bool | true only when containment and schema checks pass |
| engine | string | reelseal-runtime/v1 |

hook-check must refuse manifests that contain forbidden key URI fields or METHOD other than AES-128. On refusal exit code is 2 and accepted is false.
