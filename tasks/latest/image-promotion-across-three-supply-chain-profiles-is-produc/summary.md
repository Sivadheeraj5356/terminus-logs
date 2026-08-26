# Image promotion across three supply-chain profiles is producing inconsistent

- **UUID:** `40448e90-7afe-4bf0-bbb7-b1a41e00885c`
- **Slug:** `image-promotion-across-three-supply-chain-profiles-is-produc`
- **Category:** security
- **Difficulty:** hard

## Summary

Image promotion across three supply-chain profiles is producing inconsistent `/app/output/kv_export.json` reports. Content fingerprints disagree with the trust authority, stage transcripts fail replay checks, some runs disappear from the session export, and a mid-session loss of `/app/state/mirror_view.json` no longer yields the same export as an uninterrupted run—especially while a replica lag profile is still catching up.

The pipeline lives under `/app/environment`. Stage binaries, rebuild, and run order are in `/app/environment/docs/matrix_cmds.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
