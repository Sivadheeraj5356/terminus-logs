# Portfall is a terminal puzzle played inside a stack of shipping containers. Play

- **UUID:** `86c0da71-3a31-46ae-9e45-dfe273ebf3f8`
- **Slug:** `portfall-is-a-terminal-puzzle-played-inside-a-stack-of-shipp`
- **Category:** games
- **Difficulty:** medium

## Summary

Portfall is a terminal puzzle played inside a stack of shipping containers. Players submit command transcripts, and the game master needs an automated referee that applies the Portfall operations manual consistently instead of judging each game by hand.

Complete the Portfall game referee exposed from `/app/src` by providing `adjudicatePortfall`, `summarizePortfallLeague`, and `writePortfallAuditPack`. The referee must replay transcript text against the supplied container layout at `/app/portfall/container-spec.example.json`, follow the puzzle rules in `/app/portfall/manual.md`, and return canonical JSON using the game-state shapes in `/app/src/types.ts`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
