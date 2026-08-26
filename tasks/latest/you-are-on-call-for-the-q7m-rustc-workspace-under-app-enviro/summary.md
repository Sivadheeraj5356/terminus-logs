# You are on-call for the q7m rustc workspace under /app/environment. It replays s

- **UUID:** `bbbd91b3-64c0-402f-885d-0cb9cd93a0cc`
- **Slug:** `you-are-on-call-for-the-q7m-rustc-workspace-under-app-enviro`
- **Category:** games
- **Difficulty:** hard

## Summary

You are on-call for the q7m rustc workspace under /app/environment. It replays scripted UCI move lists and writes one JSON trace row per ply.

This first stage is observation only: do not repair the engine yet. Leave the Rust modules under /app/environment exactly as they are.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
