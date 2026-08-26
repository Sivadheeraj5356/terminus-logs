# Restore the fail-closed `PFSEAL2` cryptographic trust decision at `/app/bin/pfse

- **UUID:** `284e04c7-43cb-4ce7-b18f-f75a11d3dcc8`
- **Slug:** `restore-the-fail-closed-pfseal2-cryptographic-trust-decision`
- **Category:** security
- **Difficulty:** medium

## Summary

Restore the fail-closed `PFSEAL2` cryptographic trust decision at `/app/bin/pfseal-worker`. Every Prefect image annotation and split-key row is untrusted evidence: reject ambiguous transport, noncanonical framing, forged key-set attestations or lineage, altered headers, invalid GCM tags, cross-deployment payloads, retired or future keys, stale counters, and invalid validity windows without exposing plaintext.

Reassemble direct or chunked envelopes, require a revision-eligible 2-of-3 Ed25519 witness quorum over the canonical decoded key shares, derive independent AES-256-GCM and HMAC-SHA256 keys with the documented HKDF schedule, compare the header MAC in constant time before decryption, and authenticate any revision-bound successor proof. `/app/docs/pfseal2-wire.md`, `/app/docs/transparency-contract.md`, `/app/docs/threat-model.md`, and the failure precedence are the security contract.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
