# Transcript digest

`transcript_digest` is `sha256:` followed by the lowercase hex SHA-256 of the
UTF-8 bytes of the `events` array serialized as compact JSON with object keys
sorted lexicographically at every nesting level.
