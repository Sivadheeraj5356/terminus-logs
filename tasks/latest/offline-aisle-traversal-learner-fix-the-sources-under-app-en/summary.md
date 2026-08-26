# Offline aisle traversal learner. Fix the sources under `/app/environment`, rebui

- **UUID:** `c3ed481d-3eb2-4103-a69c-18b916844a10`
- **Slug:** `offline-aisle-traversal-learner-fix-the-sources-under-app-en`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Offline aisle traversal learner. Fix the sources under `/app/environment`, rebuild `/app/bin/lane_matrix` from that workspace (see `/app/environment/docs/artifact_rules.md` for the release build invocation), then regenerate `/app/output/coverage_map.json` with the command below.

`/app/bin/lane_matrix --fixtures /app/fixtures --spec /app/spec --out /app/output/coverage_map.json`

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
