# # PKI migration trust attestation publisher

- **UUID:** `59484a34-b822-453a-b2ff-63e33f0771fc`
- **Slug:** `pki-migration-trust-attestation-publisher`
- **Category:** security
- **Difficulty:** medium

## Summary

Certificate Transparency auditors must rebuild a Merkle row snapshot from a post-cutover migration tarball, score each CT inclusion row against revocation chronology and signed-tree-head epochs, then publish a seal-bound ledger whose combined digest binds the snapshot row order. After a botched certificate authority cutover, compliance teams inherit tarball directories that interleave X.509 material, Certificate Transparency log excerpts, signed tree heads, Merkle audit paths, revocation chronologies, issuance journals, and SHA-256 manifest ledgers.

Some rows were re-issued under the same serial, some proofs attest inclusion in a tree size that no longer matches the bundled STH, and several filenames contain ASCII spaces that naive shell iterators mishandle.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
