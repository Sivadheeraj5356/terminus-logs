# Analyze `/app/xwing-data/input/candidate_layouts.tsv` and deliver three data pro

- **UUID:** `1dd3732a-b566-417d-9608-a153866b53eb`
- **Slug:** `analyze-app-xwing-data-input-candidate-layouts-tsv-and-deliv`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Analyze `/app/xwing-data/input/candidate_layouts.tsv` and deliver three data products: `/app/out/fish_targets.tsv`, `/app/out/fish_ratings.tsv`, and `/app/out/fish_summary.json`. The input has `name` and `candidate_spec`; a spec uses semicolon-separated `digit:cells` groups and comma-separated `r1c1` cells, with repeats treated as set entries.

The target ledger header is `name\tdigit\ttarget\tsize\tfamily\tfin_state\tbase_houses\tcover_houses\texo_fins\tendo_fins\tcannibalistic`. Emit one row per selected target, ordered by name, digit, row, and column.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
