# ## Task

- **UUID:** `49505eba-bfe8-463e-8a1d-6e690a89810a`
- **Slug:** `task-catalog-beta-ndj-ndjson-one-json-object-per-line-with-a-leader-string-and-a`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

catalog_beta.ndj (NDJSON): one JSON object per line with a leader string and a fields array. A field is either control (tag plus value) or data (tag, ind1, ind2, subfields array of code and value).

catalog_gamma.fwt (fixed width): leader lines are `LEADER:` followed by the 24 char leader. Field lines are `TAG=nnn LEN=llll OFFS=ooooo DATA=body` where body is two indicators plus dollar subfields for data tags.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
