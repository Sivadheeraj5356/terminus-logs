# The 2027Q1 challenger models are stuck in the promotion queue: none of them can

- **UUID:** `dfa250ff-9b41-4ed4-94cf-efddb000d7c5`
- **Slug:** `the-2027q1-challenger-models-are-stuck-in-the-promotion-queu`
- **Category:** machine-learning
- **Difficulty:** medium

## Summary

The 2027Q1 challenger models are stuck in the promotion queue: none of them can be scored for feature drift right now, so nothing is promoted to champion this cycle and the incumbents keep serving. I need you to add that drift-screening step to the model registry as its V7 migration.

The reference data — this quarter's runs, the monitored feature catalog, the cohort register — already lives in the registry at /app/data/registry, and the stability scores the feature-audit pipeline produced, together with each run's audit lifecycle events, sit in the sealed bundle at /app/archive/fa_2027q1 behind its manifest. V7 has two jobs: ingest the bundle into a `feature_audit` table, and from the eligible observations write one row per audited run into `promotion_audit`, each ending in a PROMOTE, HOLD or REJECT determination.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
