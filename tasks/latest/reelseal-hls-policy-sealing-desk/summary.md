# # ReelSeal HLS policy sealing desk

- **UUID:** `10de653f-0913-4752-8067-d381a772d1ef`
- **Slug:** `reelseal-hls-policy-sealing-desk`
- **Category:** security
- **Difficulty:** hard

## Summary

This operational workflow on the ReelSeal facility desk under /app must deliver schema-valid encryption-manifest artifacts for AES-128 HLS sealing. Media release operators migrate sealing away from the legacy YAML and TOML configs under /app/legacy.

Those configs describe HLS outputs but leak key URIs and omit release provenance. Security reviewers require a packaged release that satisfies the cited contracts.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
