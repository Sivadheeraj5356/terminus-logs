# ReelSeal HLS policy sealing desk

This operational workflow on the ReelSeal facility desk under /app must deliver schema-valid encryption-manifest artifacts for AES-128 HLS sealing. Media release operators migrate sealing away from the legacy YAML and TOML configs under /app/legacy. Those configs describe HLS outputs but leak key URIs and omit release provenance. Security reviewers require a packaged release that satisfies the cited contracts.

The image already ships a partially implemented Gin policy API, a Go command pipeline, FFmpeg tooling, an offline Big Buck Bunny media-cache object that stands in for the historical GCS sample, git hook stubs, and GPG release material. Network access is disabled; media must be taken from the local media-cache mirror. Archival helpers under /app/decoy are outside the sealing path.

## Required security artifacts

After a full desk run:

- /app/state/media-fetch.json — fetch receipt bound to the media-cache object digest
- /app/state/hls/ — AES-128 HLS playlist and segments produced by FFmpeg
- /app/state/hls/index.m3u8 — VOD playlist under the HLS tree
- /app/state/policy-bind.json — key identifier and signing policy resolved from the Gin API with schema reelseal.policy-bind/v1
- /app/output/encryption-manifest.json — schema-valid sealed manifest without leaked key URIs
- /app/state/validation-stamp.json — hook-accepted validation stamp over the manifest bytes
- /app/state/release-attest.json — provenance attestation recorded through the policy API
- /app/output/release-package.tar — packaged artifacts gated on a GPG-signed release tag

Drive /app/scripts/reelseal-desk.sh with fetch, segment, policy-bind, seal-manifest, hook-check, release-tag, package (or run-all). Rebuild with /app/scripts/rebuild-reelseal.sh. Start the policy API with /app/scripts/start-policy-api.sh. Digest helpers live under /app/tools/digest_util.py. The desk talks to the Gin API at REELSEAL_API (default http://127.0.0.1:8742).

## Authoritative contracts

Behavior is defined only in /app/docs/reelseal-ops-brief.md, /app/docs/media-cache-fetch.md, /app/docs/hls-aes128-segment.md, /app/docs/gin-policy-api.md, /app/docs/encryption-manifest-schema.md, /app/docs/key-uri-containment.md, /app/docs/validation-stamp-contract.md, /app/docs/release-attest-contract.md, /app/docs/gpg-tag-gate.md, /app/docs/git-hook-gate.md, /app/docs/legacy-config-decoy.md, /app/docs/engineering-problem-contract.md, /app/docs/policy-bind-contract.md, and /app/docs/fixture-roster.md. Short contracts and the live Gin helpers under /app/policyapi are authoritative over handbook samples that disagree.

Desk policy binding uses /app/fixtures/profiles/roster.json as the authoritative roster; /opt/verifier-fixtures is verifier-only and is outside the desk binding path.

Operator tooling under /app/tools may use hashlib, tarfile, and urllib for local digest and archive checks.
