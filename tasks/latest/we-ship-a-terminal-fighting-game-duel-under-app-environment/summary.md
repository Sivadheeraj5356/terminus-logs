# We ship a terminal fighting-game duel under `/app/environment`: two fighters on

- **UUID:** `c0571e0c-06e6-4501-8833-59af324838d6`
- **Slug:** `we-ship-a-terminal-fighting-game-duel-under-app-environment`
- **Category:** games
- **Difficulty:** hard

## Summary

We ship a terminal fighting-game duel under `/app/environment`: two fighters on a line, integer tick physics, and online match play where the opponent's inputs arrive a few frames late. Complete the movement and combat simulation plus the predicting match client so every competitive tape stays bit-identical between the authoritative host and the online client.

Build and run:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
