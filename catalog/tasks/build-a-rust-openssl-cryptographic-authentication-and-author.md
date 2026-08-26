# Build a Rust/OpenSSL cryptographic authentication and authorization binary that 

Submission: `399830db-a4cc-4f67-8070-71e5fe5f1b79`  
Slug: `build-a-rust-openssl-cryptographic-authentication-and-author`  
Latest archive: `399830db-a4cc-4f67-8070-71e5fe5f1b79_submission_2026-07-19T19_34_20.399Z.zip`  
Revisions in Dropbox: 1

## Task summary

Build a Rust/OpenSSL cryptographic authentication and authorization binary that defends a sealed pathology vault against forged ECDSA claims, unauthorized AES-GCM plaintext disclosure, tampered attestation artifacts, and patient-identifier exfiltration. This is a security enforcement utility (signature verification, decrypt ACL, fail-closed key checks, integrity signing, confidentiality), not a reporting or analytics job. Compile `/app/bin/seal_authz` from `/app/vault_scaffold` using OpenSSL + SQLite crates and the offline vendor tree at `/opt/cargo-vendor`. With no arguments, re-read live `/app/data` each run and enforce:

Required artifacts include: `/app/bin/seal_authz`, `/app/vault_scaffold`, `/app/data`, `/app/data/sealed/`, `/app/data/keys/archive_verify.pub`, `/app/data/policy.json`, `/app/data/keys/label_dek.bin`, `/app/output`.

Author anonymous tagged this **hard** security task (openssl, ecdsa, aes-gcm, cryptography, authentication, authorization, fail-closed, rust).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `399830db-a4cc-4f67-8070-71e5fe5f1b79_submission_2026-07-19T19_34_20.399Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
