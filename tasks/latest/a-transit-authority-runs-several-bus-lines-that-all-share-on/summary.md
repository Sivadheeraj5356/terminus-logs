# A transit authority runs several bus lines that all share one common headway: ev

- **UUID:** `a9ecc381-19d3-4e47-ba9d-80a185d149bb`
- **Slug:** `a-transit-authority-runs-several-bus-lines-that-all-share-on`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A transit authority runs several bus lines that all share one common headway: every line repeats on the same fixed cycle length, and the only thing left to decide for each line is its departure offset within that cycle. Every line calls at one interchange, landing at a platform of the concourse partway through its run and pulling out again from another platform a little later, both at times fixed by the line's offset plus its known running times.

Each row of the transfer list is a body of passengers off one line who want another. They have to cross the concourse on foot, and that walk eats into the time they have to make the connection; the interchange's passage map gives the time of each passage running directly between a pair of platforms, in a building that grew piecemeal and confines nobody to a single passage.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
