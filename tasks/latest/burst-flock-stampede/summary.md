# Burst flock stampede

- **UUID:** `04ed43e8-25e6-4089-b68c-49eb73a0da17`
- **Slug:** `burst-flock-stampede`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Burst flock stampede After a host power blip, bringing several dependent host units up in the same window sometimes leaves the published volatile workspace inconsistent: one coordinator reports active while a downstream job logs that the workspace marker is held busy. Starting each unit alone recovers cleanly.

A rotation-heavy downstream log buffer hides earlier lines within minutes.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
