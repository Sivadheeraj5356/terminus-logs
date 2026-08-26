# Our measurement pipeline profiles empirical histograms whose true modes come

- **UUID:** `c18f1318-f665-4c53-b327-6b60ba06f3ef`
- **Slug:** `our-measurement-pipeline-profiles-empirical-histograms-whose`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

Our measurement pipeline profiles empirical histograms whose true modes come out oversplit by sampling noise, and the consolidation has to be self-consistent — this is a fixed-point statistics computation, not a general data-processing utility. Every bin first climbs to the lowest-position heaviest bin inside its radius window, looking again from each stop until it settles, which yields the initial modes and their basins.

Then the weak modes dissolve in rounds: the mass bar is derived from the surviving mode count itself — the floor of the total mass over the sharpness times the number of survivors — every basin strictly under the bar dissolves at once, each dissolved basin is handed whole to the surviving mode nearest its own mode with ties to the lower position, and the bar is recomputed from the shrunken mode set, so one dissolution can drag further modes under on the next pass. An optional guard directive caps how many dissolved basins a given mode may ever absorb across the whole run, and once that cap is spent the nearest search has to walk past it to the next eligible mode.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
