# Each structure in this dataset is a small square integer scalar field sampled on

- **UUID:** `494c10a4-88c1-4e7f-80d9-acdb95de0926`
- **Slug:** `each-structure-in-this-dataset-is-a-small-square-integer-sca`
- **Category:** machine-learning
- **Difficulty:** medium

## Summary

Each structure in this dataset is a small square integer scalar field sampled on a triangulated grid, the kind of coarse height map or density slice that arises in shape analysis. Its shape is summarized by a topological signature read from the persistence of the field: as a threshold sweeps through the values, connected components and loops are born and later die, and the spans from birth to death encode the structure's fold.

This is a fold-recognition problem. Each reference structure carries a known fold group; the queries do not.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
