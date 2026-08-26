# Canonical JSON hashing

All hash fields in the cascade simulator use canonical JSON stringification followed by SHA-256.

## Canonical stringify rules

1. Objects: sort keys lexicographically. Format: {"key1":val1,"key2":val2}
2. Arrays: [elem0,elem1,...] — no spaces
3. Strings: double-quoted, JSON-escaped
4. Numbers: default JSON.stringify representation (no trailing zeros forced)
5. Booleans: true or false (unquoted)
6. null: null

No whitespace between tokens. Keys are always sorted recursively at every nesting level.

## SHA-256

After canonical stringification, compute SHA-256 of the UTF-8 encoded string and represent as lowercase hexadecimal.

## Self-referencing hashes

When computing a hash of a structure that contains its own hash field (like staging_hash), set that field to empty string "" before stringifying, then write the computed digest back.
