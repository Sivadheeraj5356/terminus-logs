Milestone 3 — Verify Flask Audit Receipts

Add a Flask transparency-log API that records signed manifests in an append-only, hash-chained audit log and returns verifiable receipts.

Implement the append-only log in a flat module at exactly /app/transparency/log.py and the Flask app at exactly /app/transparency/app.py, exposing a create_app(log_path=None) factory (importable as from app import create_app with /app/transparency on sys.path — use flat imports, not package-relative ones).

The log_path argument controls where the append-only log lives. When log_path is None (the default), the log is held purely in memory and every call to create_app() returns a fresh, isolated, empty log — no state is shared between apps and nothing is read from or written to disk. When log_path is a path, entries are persisted to (and reloaded from) that file. Use an explicit path only when you want persistence (for example, the demo); never fall back to a default on-disk location when log_path is None.

There are three endpoints. POST /signatures takes a body of the form {manifest, signature, public_key_pem} (an optional manifest_hash may also be supplied). The server recomputes the canonical SHA-256 digest of manifest and verifies the Ed25519 signature over the ASCII bytes of the lowercase 64-character hex digest string (the same bytes signed in milestone 2 — digest_hex.encode("ascii"), not the raw 32 digest bytes) using public_key_pem; on success it appends an entry to the log and returns {"receipt": <entry>} with HTTP 200. GET /receipts/<index> returns {"receipt": <entry>} for that log index with HTTP 200, or HTTP 404 if the index does not exist. GET /audit returns {"entries": [...], "chain_valid": <bool>}.

Each log entry is {index, prev_hash, manifest_hash, signature, entry_hash}. The log is append-only and hash-chained: entry 0's prev_hash is 64 zeros (genesis); every later entry's prev_hash equals the previous entry's entry_hash.

The entry_hash is the lowercase hex SHA-256 of the compact canonical JSON of the entry's four committed fields — index (integer), manifest_hash, prev_hash, signature — serialized with keys sorted lexicographically and separators comma and colon (no insignificant whitespace), encoded as UTF-8. Concretely it is the SHA-256 of {"index":<int>,"manifest_hash":"<hex>","prev_hash":"<hex>","signature":"<b64>"}. The entry_hash must be recomputable from those four fields by anyone, so it cannot be an arbitrary value — receipts are checked by recomputing it.

The server must reject the following. An invalid Ed25519 signature returns HTTP 400. A supplied manifest_hash that does not match the server's computation (a tampered manifest) returns HTTP 400. A replayed (manifest_hash, signature) pair already in the log returns HTTP 409.

Demonstrate by submitting the milestone-2 signature for /app/data/manifest.json, writing the full JSON response body (the whole {"receipt": <entry>} object, not just the inner entry) to /app/out/receipt.json, and the audit log to /app/out/audit.json.
