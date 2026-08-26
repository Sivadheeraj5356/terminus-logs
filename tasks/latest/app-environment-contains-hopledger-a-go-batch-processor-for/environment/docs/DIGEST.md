# Digest rules

`digest.txt` is one lowercase SHA-256 hex line plus newline.

The digest is computed over canonical JSON containing:

- the full report object, with sorted keys recursively;
- the exact `raw_input_digest`;
- the exact `policy_lineage_digest`;
- all audit decisions as canonical JSON objects in order.

`raw_input_digest` is a lowercase SHA-256 hex digest of the UTF-8 canonical JSON payload with no trailing newline before hashing. The payload is an array, in manifest lane order, with one object per nonblank raw journal line: `{"lane": <lane name or "">, "priority": <lane priority or 0>, "line": <zero-based nonblank line index within that lane file>, "raw": <exact raw line text>}`. Canonical JSON sorts object keys recursively and uses compact separators with no extra whitespace.
