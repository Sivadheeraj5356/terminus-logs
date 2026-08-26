# Gin policy API contract

Base URL: http://127.0.0.1:8742 (override with environment variable REELSEAL_API)

## GET /health
Returns {"ok":true,"engine":"reelseal-runtime/v1"}

## POST /v1/profiles/resolve
Request JSON: {"profile_id": string, "expected_epoch": int}
Success 200: {"profile_id","epoch","signing_alg","allowed_algs"}
Reject 409 when expected_epoch does not equal the roster epoch for that profile.

## POST /v1/keys/issue
Request JSON: {"profile_id": string, "media_digest": string, "purpose": "hls-aes128"}
Success 200: {"key_id": string, "key_urn": "urn:reelseal:key:<key_id>", "profile_epoch": int}
Responses must not include key_uri, key_url, or http(s) locations.

## POST /v1/attest/release
Request JSON: {"key_id","media_digest","playlist_digest","policy_digest","manifest_digest","release_tag"}
Success 200: {"attest_id","bound": true, "engine":"reelseal-runtime/v1"}
Reject 400 when any digest is empty or key_id is unknown.

Default profile_id is reel-std from /app/fixtures/profiles/roster.json.
