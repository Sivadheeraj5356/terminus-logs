# Trickfall Matchbook Arena

- **UUID:** `4cef8e9c-2a77-43cf-8668-59551b8543e0`
- **Slug:** `trickfall-matchbook-arena`
- **Category:** games
- **Difficulty:** hard

## Summary

Trickfall Matchbook Arena Create `/app/matchbook/matchbook`, an offline Rust command-line analyst for adversarial Trickfall endgames. Its interface is `./matchbook solve FILE`, where FILE follows the matchbook protocol at `/app/matchbook/spec.md` and may contain several independent cases.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
