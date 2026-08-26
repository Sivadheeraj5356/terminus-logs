Build a Node.js certificate worker (/app/src/worker.js) that manages a 2-tier PKI hierarchy, automates certificate lifecycle, and enforces cryptographic integrity constraints. The worker must support flags --ledger <path> (CSV service list) and --pki-dir <path> (PKI storage directory, defaults to /app/data/services.csv and /app/pki).

## Core Requirements

**Multi-Tier PKI & Certificate Issuance**
Implement a two-tier CA: root CA in `pki-dir/ca/` (`ca.key.pem`, `ca.crt.pem`), and per-service intermediate CAs (in `pki-dir/services/<service>/`). Each service's intermediate is signed by root; service certificates are signed by their intermediate (not root). Issue service certificates with exactly 90-day validity.

**Staging & Temporal Constraints**
Do not issue a service certificate until its intermediate has existed for ≥7 days. On first run, create both intermediate and certificate if ready; else report action="staged" (staged_at as an ISO-8601 UTC string, no cert_path/key_path). Subsequent runs issue once the 7-day window passes. Intermediates themselves have 365-day validity; when expired, create a new intermediate with a fresh key.
Persist `int_created_at` as a decimal Unix timestamp integer (seconds since epoch, UTC), for example `1720213734`.

**Algorithm Lock-In**
Once a service's first certificate is issued, enforce the same key_algorithm (rsa or ec) for all future rotations. Reject changes (error code="algorithm_mismatch").

**Serial Number Sequencing**
Assign monotonically increasing serial numbers per service. Track the last-issued serial; each new certificate must have serial > previous. Reject if this constraint is violated.
Persist this value in `pki-dir/services/<service>/.serial` as a lowercase hexadecimal string (no `0x` prefix). On every issuance/rotation, the `.serial` value must be hex-equivalent to the serial embedded in the current `cert.pem`.

**Cryptographic Integrity**
Verify the certificate chain after issuance (service cert signed by intermediate, intermediate signed by root). Reject with error code="chain_validation_failed" if verification fails. Maintain an immutable certificate manifest (one entry per issuance/rotation/reuse) recording serial, issued_at, expires_at, action, public_key_sha256, prev_entry_hash, entry_hash, and entry_sig. For each entry, canonicalize exactly these fields: {action, expires_at, issued_at, prev_entry_hash, public_key_sha256, serial}; then compute entry_hash = SHA256(canonical_json) and entry_sig = HMAC-SHA256(manifest_secret, canonical_json) as lowercase hex. Define manifest_secret as raw bytes: `sha256(("manifest:" + service + ":" + first_line_of_.int_key_hashes).utf8_bytes)`, and use those bytes directly as the HMAC key (do not hex-encode first). prev_entry_hash is "" for the first entry and otherwise equals the prior entry's entry_hash. On every run, verify ordered issued_at, hash-chain continuity, per-entry signatures, latest-entry public key hash match, and rotated key non-reuse; reject with error code="manifest_mismatch" on any violation.

**Intermediate Key Rotation Integrity**
Track all intermediate key fingerprints ever used per service. When rotating an intermediate (creating a new one after expiry), the new key's SHA-256 fingerprint must not exist in the service's key history. Reject with error code="rotated_key_reuse" if key reuse is detected.

**Audit Trail with Cryptographic Signing**
Log every certificate operation (issued, rotated, reused) to `pki-dir/audit.log` (NDJSON, one JSON object per line). Each entry contains: service, action, key_algorithm, expires_at, timestamp (ISO-8601), `prev_hash`, `entry_hash`, audit_signature (hex HMAC-SHA256), audit_day (floor(unix_timestamp / 86400)). Build a hash chain: `entry_hash = sha256(canonical_json)`, `prev_hash` equals the previous entry's `entry_hash` (or `""` for the first entry). Canonical audit payload must include exactly these fields for hash/signature input: {service, action, key_algorithm, expires_at, timestamp, prev_hash}; exclude `audit_day`, `entry_hash`, and `audit_signature` from canonical input. Compute audit_signature as HMAC-SHA256 over canonical JSON (sorted keys, compact) with a daily-rotated key: read AUDIT_SEED from environment (default 42), derive AUDIT_SECRET = SHA256('cert-audit-{AUDIT_SEED}'), compute daily_key = HMAC-SHA256(AUDIT_SECRET, str(audit_day)). On every run, verify all existing audit log entries by recomputing signatures and validating `prev_hash`/`entry_hash` continuity; reject with error code="invalid_signature" if any check fails.

**Certificate Revocation & Chain Validation**
When rotating a service certificate, record the previous certificate as revoked in the intermediate CA's revocation database, then generate/update a CRL at `pki-dir/services/<service>/crl.pem` signed by that intermediate. The CRL must contain the revoked certificate's serial number.

**Output Schema**
Return status="ok" and processed array (sorted by service name). For issued/rotated/reused actions: include service, action, key_algorithm, cert_path, key_path, expires_at, public_key_sha256. For staged: include service, action="staged", staged_at, serial (hex, next-to-be-issued). Error: status="error", code (invalid_key_algorithm, algorithm_mismatch, invalid_signature, chain_validation_failed, manifest_mismatch, rotated_key_reuse).
For any status="error" response, exit with a non-zero process code.

**Idempotency**
Multiple runs must produce consistent output. Reuse semantics: action="reused" if certificate is valid and rotate_before_days condition not met. Action="rotated" if remaining validity < rotate_before_days. On rotation, overwrite cert.pem/key.pem. Audit log entries are immutable and cryptographically verified before processing.

## Implementation Reference

**File Modes:** `pki-dir/ca/ca.key.pem` = 0600, `pki-dir/ca/ca.crt.pem` = 0644, int.key.pem = 0600, int.crt.pem = 0644, key.pem = 0600, cert.pem = 0644, .serial = 0644, int_created_at = 0644, .int_key_hashes = 0644, audit.log = 0644, crl.pem = 0644, manifest.json = 0644.

**CSV Schema:** service, hostname, sans, key_algorithm, rotate_before_days. Generate intermediate CN as {service}-int, root CN as openssl-ca-root, service certs CN=hostname with SANs.

**Manifest Format:** `{"service": "...", "issued_certificates": [{"serial": "...", "issued_at": "...", "expires_at": "...", "action": "...", "public_key_sha256": "...", "prev_entry_hash": "...", "entry_hash": "...", "entry_sig": "..."}, ...]}`.

**Public Key SHA256:** Hash the raw PEM-encoded text output of `openssl x509 -pubkey -noout` (including all newlines and headers), encoded as UTF-8 bytes before hashing.
