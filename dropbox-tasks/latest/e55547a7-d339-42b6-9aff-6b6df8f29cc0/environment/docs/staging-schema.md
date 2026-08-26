# Staging schema

The staging envelope at /app/state/cascade-staging.json has these fields:

- mission_slot: string from manifest (or CASCADE_MISSION_SLOT override)
- manifest: the full manifest object
- bodies: array of body objects in feed order (as loaded from bodies.jsonl line by line; not sorted)
- flares: array of flare events sorted by t_sec ascending
- catalog_fingerprint: sha256 hex digest of the concatenation of raw bodies.jsonl bytes followed by raw flares.jsonl bytes
- staging_hash: canonical JSON hash of the staging envelope with staging_hash set to empty string during computation

The staging_hash is computed by:
1. Build the full envelope object
2. Set staging_hash to ""
3. Canonical-stringify the object (keys sorted recursively, no whitespace)
4. SHA-256 hex digest of the canonical string
5. Write the digest back into staging_hash

Canonical stringify rules:
- Objects: sort keys lexicographically; format as {"key1":value1,"key2":value2}
- Arrays: [elem1,elem2]
- Strings: JSON-escaped with double quotes
- Numbers: JSON.stringify representation
- Booleans: true/false
- null: null
