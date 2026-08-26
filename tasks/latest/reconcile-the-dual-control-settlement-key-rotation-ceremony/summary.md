# # Reconcile the dual-control settlement key-rotation ceremony

- **UUID:** `f97d92ac-c12e-4fa4-99b8-2a30500a3aa8`
- **Slug:** `reconcile-the-dual-control-settlement-key-rotation-ceremony`
- **Category:** security
- **Difficulty:** hard

## Summary

A primary SoftHSM2 token in `/app/ceremony` contains a retiring settlement key whose private half exists only inside that token. A second escrow token contains an escrow private key that also has no filesystem copy.

A new settlement key and certificate are staged on disk, but the primary token has no recovery envelope, continuity evidence, escrow receipt, or replacement custody objects yet. Rotate custody without resetting either token or losing unrelated objects.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
