# A candleworks clears a design for its production run only once it has thrown a c

- **UUID:** `fd313533-fb55-45aa-9a30-7883983ac956`
- **Slug:** `a-candleworks-clears-a-design-for-its-production-run-only-on`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A candleworks clears a design for its production run only once it has thrown a clean burn: one candle poured to that recipe, burning down to a full even melt pool, no channel tunnelled through the middle, no soot off the wick, no drowned flame. Forty recipes are up for the coming run, `cd-01` through `cd-40` in /app/environment/data/designs.csv, and pouring is not repeatable to the last detail: the wick sits a hair off centre one time and true the next, so one candle off a recipe can burn clean where the one before it faulted.

Each design therefore has a clean-burn rate `p` of its own that no single candle reveals, and pouring `n` candles to it lands at least one clean burn with probability `1 - (1 - p)^n`. For every design you return two counts, how many candles for the in-house line and how many for the outside chandler.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
