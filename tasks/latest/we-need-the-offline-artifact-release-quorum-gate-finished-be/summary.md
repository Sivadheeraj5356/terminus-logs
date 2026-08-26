# We need the offline artifact release quorum gate finished before custody can sig

- **UUID:** `36251034-f9a0-4a08-bdf2-9f9f16570311`
- **Slug:** `we-need-the-offline-artifact-release-quorum-gate-finished-be`
- **Category:** security
- **Difficulty:** hard

## Summary

We need the offline artifact release quorum gate finished before custody can sign off on binary promotions. The Zig tree under `/app` already compiles to `/app/bin/quorumgate`, but evaluation is still stubbed — nothing checks the Ed25519 counter-signatures or weighted quorum math from the contracts.

Read `/app/docs/format.md`, `/app/docs/sign_contract.md`, and `/app/docs/digest_contract.md`. Bundled packs are under `/app/data/bundles/`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
