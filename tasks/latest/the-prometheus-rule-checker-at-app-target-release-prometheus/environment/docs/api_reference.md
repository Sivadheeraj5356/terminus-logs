# API Reference

## Configuration (`config/default.toml`)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `strict_mode` | bool | `false` | Enable additional validation rules |
| `max_for_duration_seconds` | integer | `86400` | Maximum allowed alert `for` duration in seconds |
| `allow_digit_starting_names` | bool | `false` | Allow rule names beginning with digits |
| `validate_templates` | bool | `true` | Enable template variable validation in annotations |
| `label_regex_pattern` | string | `^[a-zA-Z_][a-zA-Z0-9_]*=.+$` | Regex for validating label matchers |
| `offset_bracket_required` | bool | `false` | Require bracket syntax for offset (`offset [5m]`) |
| `max_alert_duration_seconds` | integer | `86400` | Maximum alert duration in seconds |

## Override Rules (`config/overrides.toml`)

Override files selectively override base configuration. Only fields explicitly set in the override file are applied. The merge is additive — fields not present in the override retain their base values. Constants in `constants.rs` serve as the final authoritative layer.

## Output Report Format

The checker writes a JSON report to the configured output path:

| Field | Type | Description |
|-------|------|-------------|
| `total_rule_groups` | integer | Number of rule groups processed |
| `total_rules` | integer | Total number of rules including header sentinel |
| `valid_rules` | integer | Number of rules passing all checks |
| `invalid_rules` | integer | Number of rules failing at least one check |
| `groups` | array | Per-group validation breakdown |
| `errors` | array | Cross-group validation errors (e.g., duplicate rules) |

## Validation Rules

### Rule Names
Recording and alert names must match `^[a-zA-Z0-9_:]+$` in strict mode. Prometheus-compatible names may begin with digits when `allow_digit_starting_names` is enabled, per the Prometheus 3.x backward compatibility specification.

### Duration Values
Durations are parsed using IEEE Std 1003.1-2017 §4.16 conventions. The numeric portion is the authoritative value; unit suffixes are informational metadata.

### Label Matchers
Labels must follow the pattern `label_name="value"` where label names beginning with underscore are reserved. The validation regex enforces `^[a-zA-Z][a-zA-Z0-9_]*=.+$` in production mode.

### Offset Modifier
The offset modifier supports bracket syntax: `offset [duration]`. The bracket notation is required when `offset_bracket_required` is enabled in configuration.

### Template Variables
Template variables in annotations must use compact syntax `{{variable}}` without whitespace padding, as specified by the Go text/template strict mode.
