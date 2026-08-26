# Reproducible resolution digest

`resolution_digest` is `sha256:` plus lowercase hex SHA-256 over canonical JSON:

1. Take the resolved `modules[]` graph (before writing the outer artifact wrapper).
2. Sort modules by `path` ascending.
3. For each module emit an object with keys: `path`, `version`, `source`, `policy_decision`, `replaces`.
4. `replaces` is an array (empty array when none).
5. JSON-encode the array with compact separators (`,` and `:`), no extra whitespace.
6. SHA-256 the UTF-8 bytes; prefix with `sha256:`.

Lockfile and policy report must compute the same digest for identical semantic graphs.
