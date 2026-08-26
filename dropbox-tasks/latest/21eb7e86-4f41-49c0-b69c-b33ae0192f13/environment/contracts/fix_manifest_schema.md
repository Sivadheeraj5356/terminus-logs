# Fix manifest schema

`bastion-audit repair` writes JSON to the path given by `--manifest`.

| Field | Type | Meaning |
|-------|------|---------|
| `staging_root` | string | Absolute path to extracted staging tree |
| `tenant` | string | Tenant id used for registry overlay |
| `changes` | array | Regular **files** whose **content bytes** were rewritten this run |
| `noop` | boolean | `true` when `changes` is empty |
| `manifest_sha256` | string | Lowercase hex SHA-256 digest (see below) |

Each change object:

| Field | Type | Meaning |
|-------|------|---------|
| `path` | string | Relative path under staging root |
| `before_sha256` | string | Lowercase hex SHA-256 of file bytes before repair |
| `after_sha256` | string | Lowercase hex SHA-256 of file bytes after repair |

**Mode-only repairs:** `bastion:file_modes` may include directory paths (for example `homes/alice/.ssh`). When repair corrects permissions with `chmod` and the path is a directory or a file whose byte content is unchanged, that path must **not** appear in `changes`. Only content rewrites produce change entries, and every listed change must have distinct `before_sha256` and `after_sha256` digests.

## manifest_sha256 computation

1. Let `changesSorted` be a copy of `changes` sorted by ascending `path` (lexicographic).
2. Serialize **only** the array `changesSorted` as compact JSON with no insignificant whitespace — equivalent to JavaScript `JSON.stringify(changesSorted)` or Python `json.dumps(changesSorted, separators=(",", ":"))`.
3. `manifest_sha256` = lowercase hexadecimal SHA-256 of the UTF-8 encoding of that byte string.

Do **not** hash the full manifest object, pretty-printed JSON, or an unsorted `changes` array.

**Idempotency:** a second repair on an already-correct tree must emit `noop: true`, an empty `changes` array, and `manifest_sha256` computed over that empty sorted array.

Mode comparisons normalize octal strings (`750` equals `0750`) per `bastion_access_handbook.md`.
