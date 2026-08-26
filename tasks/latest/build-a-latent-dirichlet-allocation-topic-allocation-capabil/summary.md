# Build a Latent Dirichlet Allocation topic-allocation capability under /app on th

- **UUID:** `a2065d0a-7c9d-46db-b8ad-7d363f047d25`
- **Slug:** `build-a-latent-dirichlet-allocation-topic-allocation-capabil`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Build a Latent Dirichlet Allocation topic-allocation capability under /app on the supplied working Rust workspace. Implement patent document ingest, corpus staging, a deterministic collapsed-Gibbs sampler, a posterior count ledger, and a sealed topic rollup export according to /app/docs/cli.md, /app/docs/document-format.md, /app/docs/vocabulary.md, /app/docs/initialization.md, /app/docs/conditional.md, /app/docs/count-ledger.md, /app/docs/burn-in.md, /app/docs/topic-ranking.md, /app/docs/rollup-export.md, /app/docs/decoy-tfidf.md, and /app/docs/crate-modules.md.

ldactl ingest reads JSON patent documents from the configured inbox and writes /app/state/lda-corpus-staging.json. ldactl sample reads only that corpus snapshot, runs the collapsed-Gibbs sampler, and writes /app/state/lda-count-staging.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
