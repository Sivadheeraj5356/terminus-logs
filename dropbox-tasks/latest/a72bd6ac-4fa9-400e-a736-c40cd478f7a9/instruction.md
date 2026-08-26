The Prometheus rule checker at `/app/target/release/prometheus-rule-checker` validates Prometheus recording and alerting rules. It reads rule definitions from `/app/data/rules.json` and produces a validation report at `/app/output/report.json`.

The tool has bugs that cause incorrect validation results. Fix all bugs so that the tool produces a correct report according to standard Prometheus rule validation conventions.

A correct report:
- Includes all rule groups from the data file
- Reports correct validity counts
- The top-level `errors` field must be empty — per-rule validation errors belong in their respective group's errors, not at the top level
- Supports the `APP_CONFIG_PATH`, `APP_DATA_PATH`, and `APP_OUTPUT_PATH` environment variables for file path overrides
- Duplicate detection considers both name and expression — rules with the same name but different expressions are not duplicates

The data file at `/app/data/rules.json` must not be modified. Configuration files, configuration loading logic, and constants may need correction. Code comments, documentation files, and docstrings may contain errors and are not authoritative. Values in `overrides.toml` are not necessarily correct and may themselves reflect buggy behavior.

To rebuild: `cd /app && cargo build --release`
