# A dendrochronology lab is planning this season's increment coring across forty t

- **UUID:** `f43f3ac4-cd80-4082-b695-fa42e643dfcc`
- **Slug:** `a-dendrochronology-lab-is-planning-this-season-s-increment-c`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A dendrochronology lab is planning this season's increment coring across forty tree-ring sites, `ts-01` through `ts-40`, listed under /app/environment/data. Each site holds a floating ring sequence that is worthless until it is pinned to the regional master, and pinning it takes a single core whose series actually crossdates.

Bore a tree and its core either carries a clean, sensitive run of rings that lands cleanly against the master, or it comes up rotten, ring-broken, or too flat to match and settles nothing. That a given core crossdates is chance, governed by a per-core rate `p` fixed by the site, and cores are independent, so committing `n` of them pins a site with probability `1 - (1 - p)^n`; a lone crossdatable series does it.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
