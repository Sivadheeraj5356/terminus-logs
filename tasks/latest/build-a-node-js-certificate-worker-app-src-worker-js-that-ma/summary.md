# Build a Node.js certificate worker (/app/src/worker.js) that manages a 2-tier PK

- **UUID:** `5fdf58a3-9ca9-40d6-aa68-b54a30c666c3`
- **Slug:** `build-a-node-js-certificate-worker-app-src-worker-js-that-ma`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Build a Node.js certificate worker (/app/src/worker.js) that manages a 2-tier PKI hierarchy, automates certificate lifecycle, and enforces cryptographic integrity constraints. The worker must support flags --ledger <path> (CSV service list) and --pki-dir <path> (PKI storage directory, defaults to /app/data/services.csv and /app/pki).

**Multi-Tier PKI & Certificate Issuance** Implement a two-tier CA: root CA in `pki-dir/ca/` (`ca.key.pem`, `ca.crt.pem`), and per-service intermediate CAs (in `pki-dir/services/<service>/`). Each service's intermediate is signed by root; service certificates are signed by their intermediate (not root).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
