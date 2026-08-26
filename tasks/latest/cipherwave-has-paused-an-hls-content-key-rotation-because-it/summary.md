# Cipherwave has paused an HLS content-key rotation because its signature, custody

- **UUID:** `65e96c3c-58a3-4c78-8943-e6ee43dc326a`
- **Slug:** `cipherwave-has-paused-an-hls-content-key-rotation-because-it`
- **Category:** security
- **Difficulty:** hard

## Summary

Cipherwave has paused an HLS content-key rotation because its signature, custody, fragment-integrity, rollout-ledger, quorum, and authorization evidence does not initially agree. The required work product is the fixed incident's cryptographic security ruling, derived offline from the immutable `profile.toml`, `registry.json`, `trust.json`, `catalog.json`, `guardian-trust.json`, `rollout-ledger.json`, and complete `media/` tree under `/app/fixtures/visible`.

The profile audit time is the sole time authority; wall-clock time, network data, environment variables, and bundled output are not trust sources. The complete normative contract is split across three documents that must be applied together: `/app/docs/security-contract.md` defines authentication, key custody, HLS evidence, lifecycle and decision precedence, rollout-ledger replay, checkpoint classification, the complete frontier, and resilient authorization; `/app/docs/artifact-contract.md` defines exact schemas, canonical bytes, ordering, nullability, digests, confirmations, certificate seal, and plan binding; `/app/docs/contract-map.md` defines authority roles, trust boundaries, registry semantics, deliverable boundaries, and the retained-path confidentiality rule.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
