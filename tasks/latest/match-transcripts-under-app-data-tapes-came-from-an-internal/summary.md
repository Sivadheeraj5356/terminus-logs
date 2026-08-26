# Match transcripts under /app/data/tapes/ came from an internal ladder client, bu

- **UUID:** `113eaf41-5192-4eb9-a08e-de8b4d19d701`
- **Slug:** `match-transcripts-under-app-data-tapes-came-from-an-internal`
- **Category:** games
- **Difficulty:** hard

## Summary

Match transcripts under /app/data/tapes/ came from an internal ladder client, but the published rule card is gone. Repair the Rust sources under /app/environment, rebuild with /app/environment/scripts/bake_rs.sh, then run the full grid checker at /app/environment/bin/grti_matrix_k9 as described in /app/environment/docs/operators.md so every arm and grid pair passes.

Hand-writing or manually editing the witness artifact is insufficient; the normal pipeline must regenerate /app/output/rule_witness.json from repaired sources. Success means exit code 0 for all four arms (cedar, maple, birch, willow) under both band profiles (dawn, dusk).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
