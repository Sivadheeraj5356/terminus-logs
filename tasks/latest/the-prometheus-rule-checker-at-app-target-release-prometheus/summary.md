# The Prometheus rule checker at `/app/target/release/prometheus-rule-checker` val

- **UUID:** `a72bd6ac-4fa9-400e-a736-c40cd478f7a9`
- **Slug:** `the-prometheus-rule-checker-at-app-target-release-prometheus`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The Prometheus rule checker at `/app/target/release/prometheus-rule-checker` validates Prometheus recording and alerting rules. It reads rule definitions from `/app/data/rules.json` and produces a validation report at `/app/output/report.json`.

The tool has bugs that cause incorrect validation results. Fix all bugs so that the tool produces a correct report according to standard Prometheus rule validation conventions.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
