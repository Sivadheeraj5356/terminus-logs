# Engineering problem contract — ReelSeal HLS policy sealing

ReelSeal is a multi-stage offline sealing desk, not a legacy YAML/TOML copy path.

Failure modes that must remain distinct:

- Media fetch must bind the offline media-cache object digest; network pulls and /app/legacy paths are invalid sources.
- HLS AES-128 playlists must reference urn:reelseal:key URNs rather than http(s) key locations copied from decoy configs.
- Gin profile resolve rejects expected_epoch values that do not match the desk roster under /app/fixtures/profiles/roster.json.
- Policy issue responses that embed key_uri must not be copied into policy-bind or encryption-manifest artifacts.
- policy_digest must cover the nine bind fields defined in policy-bind-contract.md; omitting fields or hashing pretty-printed JSON breaks digest custody.
- Validation stamps and release attestations must bind the sealed manifest bytes; packaging without a verified GPG release tag is refused.
- /app/decoy/legacy_seal_driver.go and /app/legacy configs are archival decoys and stay off the sealing hot path.

Cross-run persistence: a second successful desk seal must issue a fresh key_id rather than reuse prior key material on unchanged fixtures.
