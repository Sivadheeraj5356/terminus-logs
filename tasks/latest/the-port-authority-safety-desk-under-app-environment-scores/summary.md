# The port authority safety desk under `/app/environment` scores a deployed fairne

- **UUID:** `c98faf14-3764-4aad-bb9f-274b89045c87`
- **Slug:** `the-port-authority-safety-desk-under-app-environment-scores`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The port authority safety desk under `/app/environment` scores a deployed fairness model on held-out evaluation rotations, running subgroup coverage evaluation and paired-label merge scoring before governance exports ship. The model evaluation pipeline is exposed at `/app/tools/k9ctl` and `/app/environment/tools/k9ctl`; regenerated evaluation artifacts must land at `/app/output/blk_k9.json` and `/app/output/trace_w8.jsonl`.

Model evaluation exports are not metric-correct today: a preflight pass on the staging slice can look healthy while held-out desk rotations in `/app/environment/fixtures/k9/w8_catalog.json` reopen subgroup undercoverage breaches during a full k9ctl score export. Prior ruling filings still leave stale score blocks in the trace after rescoring, and paired impact labels sometimes pick the wrong winner on some rotations.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
