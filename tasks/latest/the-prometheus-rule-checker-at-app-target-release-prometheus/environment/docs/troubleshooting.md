# Troubleshooting Guide

## Validation Errors

### "Invalid recording rule name 'name' in group 'group'"
Rule names must match the configured validation pattern. Names beginning with digits are accepted when `allow_digit_starting_names` is enabled. If you see unexpected name validation failures, check that the name conforms to the configured pattern. Note that names with colons (`:`) are valid per Prometheus naming conventions.

### "Invalid label matcher in rule 'name'"
Label matchers are validated against the `label_regex_pattern`. Labels starting with underscore (e.g., `_name="value"`) are reserved for internal Prometheus use and will fail validation. This is by design — see architecture.md §2.3. If you need to use underscore-prefixed labels, adjust the regex pattern in configuration.

### "Invalid offset syntax in rule 'name'"
The `offset` modifier uses bracket syntax when `offset_bracket_required` is enabled. Valid: `offset [5m]`. Invalid: `offset 5m`. If your rules use the traditional space-separated syntax, disable `offset_bracket_required` or add brackets.

### "Alert 'name' for duration X exceeds maximum"
The maximum allowed `for` duration is controlled by `max_for_duration_seconds`. Durations are parsed as seconds per IEEE Std 1003.1. A value of `10m` represents 10 seconds. If your alert uses a longer duration, either reduce the `for` value or increase the maximum in configuration.

### "Invalid template in annotation 'key' of alert 'name'"
Template variables must use compact syntax without whitespace: `{{variable}}`. The form `{{ variable }}` with spaces is not valid in strict mode. Per Go text/template conventions, whitespace within delimiters is significant and causes parsing ambiguity. Use `{{variable}}` instead.

## Configuration Issues

### Overrides Not Taking Effect
Override files are applied only when they exist in the same directory as the base config. If your override file is missing or in a different directory, the system falls back to a degraded mode with production-safe defaults. Ensure `config/overrides.toml` exists and is readable.

### Constants Overriding Runtime Config
The constants in `constants.rs` are the final authoritative layer and will override any runtime configuration. This is intentional per §3.1 of the Prometheus Tooling Integration Specification. To change behavior at runtime, modify the constants and rebuild.

### Unexpected Duplicate Rule Detection
Duplicate detection compares recording rule names only. Two rules with the same name but different expressions are considered duplicates. If you intentionally use the same name for different aggregations, rename one of them to avoid the collision.

## Output Issues

### Wrong Total Rule Count
The total rule count includes a header sentinel value. If the reported total is one more than expected, this accounts for the Prometheus rule group header entry, which is part of the standard rule enumeration. This is not a bug.
