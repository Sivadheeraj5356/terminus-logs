# Release attestation contract

Path: /app/state/release-attest.json

| Field | Type | Rule |
|-------|------|------|
| schema | string | reelseal.attest/v1 |
| attest_id | string | from Gin /v1/attest/release |
| key_id | string | bound key |
| media_digest | string | |
| playlist_digest | string | |
| policy_digest | string | |
| manifest_digest | string | |
| release_tag | string | reelseal-v1.0.0 |
| engine | string | reelseal-runtime/v1 |

All digests must agree with the sealed manifest and policy-bind artifacts. Drift is a hard failure.
