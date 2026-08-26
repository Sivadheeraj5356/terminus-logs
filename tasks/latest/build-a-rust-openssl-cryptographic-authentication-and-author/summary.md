# Build a Rust/OpenSSL cryptographic authentication and authorization binary that

- **UUID:** `399830db-a4cc-4f67-8070-71e5fe5f1b79`
- **Slug:** `build-a-rust-openssl-cryptographic-authentication-and-author`
- **Category:** security
- **Difficulty:** hard

## Summary

Build a Rust/OpenSSL cryptographic authentication and authorization binary that defends a sealed pathology vault against forged ECDSA claims, unauthorized AES-GCM plaintext disclosure, tampered attestation artifacts, and patient-identifier exfiltration. This is a security enforcement utility (signature verification, decrypt ACL, fail-closed key checks, integrity signing, confidentiality), not a reporting or analytics job.

Compile `/app/bin/seal_authz` from `/app/vault_scaffold` using OpenSSL + SQLite crates and the offline vendor tree at `/opt/cargo-vendor`. With no arguments, re-read live `/app/data` each run and enforce:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
