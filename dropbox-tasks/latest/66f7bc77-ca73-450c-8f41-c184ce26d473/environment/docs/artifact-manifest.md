# Model artifact manifest registry

Each promoted `model_id` has a release manifest under `/app/registry/manifests/<model_id>.toml`. Manifests are authoritative for which `artifact_digest` values are valid for a given `sklearn_pin`.

## File format

```toml
[[release]]
sklearn_pin = "1.4.2"
artifact_digest = "sha256:..."
```

Digest strings use a lowercase `sha256:` prefix and lowercase hexadecimal. Compare digests case-insensitively on the hex body when matching candidate rows, compose labels, and manifest entries.

## Gate

Reject with `artifact_manifest_mismatch` when no `[[release]]` row matches both the candidate `sklearn_pin` and `artifact_digest`.
