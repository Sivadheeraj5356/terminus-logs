# The hex skirmish adjudicator under `/app/environment/skirmish` resolves battle s

- **UUID:** `6ca8779f-d958-4709-88cf-e985b6f91cce`
- **Slug:** `the-hex-skirmish-adjudicator-under-app-environment-skirmish`
- **Category:** games
- **Difficulty:** hard

## Summary

The hex skirmish adjudicator under `/app/environment/skirmish` resolves battle scenarios into a deterministic transcript. Current rebuilds disagree with the rulebook on interrupt chains, vision, and armor interactions.

Repair the Rust sources under `/app/environment` so `/app/bin/skirmish` regenerates reports that match the contract below. Static report writes are not enough; the verifier rebuilds from source and re-runs adjudication.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
