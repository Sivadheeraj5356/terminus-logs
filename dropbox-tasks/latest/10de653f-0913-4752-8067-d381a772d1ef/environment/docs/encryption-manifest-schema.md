# Encryption manifest schema

Path: /app/output/encryption-manifest.json
schema: reelseal.encryption-manifest/v1

| Field | Type | Rule |
|-------|------|------|
| schema | string | exact |
| engine | string | reelseal-runtime/v1 |
| media_digest | string | matches fetch receipt |
| playlist_digest | string | sha256 of /app/state/hls/index.m3u8 bytes after URI rewrite |
| key_id | string | from /v1/keys/issue |
| key_urn | string | urn:reelseal:key:<key_id> |
| method | string | AES-128 |
| iv_hex | string | 32 lowercase hex chars |
| policy_digest | string | sha256 of canonical policy-bind JSON bytes |
| signing_alg | string | must be in allowed_algs from resolve |
| profile_epoch | int | must match resolve epoch |
| provenance.attest_id | string | from /v1/attest/release after seal, filled on package path; may be empty until attest |
| provenance.release_tag | string | reelseal-v1.0.0 |

Forbidden top-level keys: key_uri, key_url, key_http, legacy_uri.
