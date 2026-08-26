# concurrency_ordering

- **UUID:** `2c6899dd-c790-45f7-80f4-bdb3903e2958`
- **Slug:** `concurrency-ordering`
- **Category:** games
- **Difficulty:** hard

## Summary

Wrap seats on the hex lobby disagree with their flat controls for the same seed. A wrapped control seat should agree with its flat reference on final_counts, history_len, rejected_repeats, position_digests, and terminal_digest for the same seed and interior stone sequence.

Longer exchanges can leave material that should already be gone, and a saved journal can admit a repeat the live lobby would reject while still blocking some legal non-repeating moves. Repair sources under `/app` so a release rebuild of `/app/target/release/arena_cli` writes `/app/output/runs/<scenario_id>.json` from those sources.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
