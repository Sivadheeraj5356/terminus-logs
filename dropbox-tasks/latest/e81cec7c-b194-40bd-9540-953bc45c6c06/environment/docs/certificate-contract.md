# Readiness certificate

Written by `assess` to `--output-certificate`.

Fields:

- identity/digest mirrors from the report
- `all_placements_satisfied` — true iff `satisfied_placement_count == placement_request_count`
- `certificate_ok` — true iff `all_placements_satisfied` is true
- `certificate_digest` — SHA-256 of canonical compact JSON of certificate fields excluding itself
