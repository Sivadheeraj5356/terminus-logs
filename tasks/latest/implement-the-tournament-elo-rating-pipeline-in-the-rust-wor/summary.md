# Implement the tournament Elo rating pipeline in the Rust workspace under /app/en

- **UUID:** `c4f0d4fb-bc74-40cd-af5e-aabbadf7a298`
- **Slug:** `implement-the-tournament-elo-rating-pipeline-in-the-rust-wor`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Implement the tournament Elo rating pipeline in the Rust workspace under /app/environment so elo_verify emits a contract-compliant JSON report from the bundled match trace. Read /app/docs/contract.md for the output schema, /app/docs/pipeline_stages.md for stage responsibilities and workspace paths, and /app/docs/elo_formula.md for rating math and aggregate fields.

Do not modify sources under /app/environment/tools/elo_verify/ or /app/environment/traces/. The verifier writes the report to the output path specified on its command line; tests consume /tmp/test_report.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
