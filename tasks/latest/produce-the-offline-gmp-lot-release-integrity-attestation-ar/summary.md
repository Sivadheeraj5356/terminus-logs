# Produce the offline GMP lot-release integrity attestation artifacts under /app f

- **UUID:** `669a8077-6e10-4cb1-9465-e2980b59d1d9`
- **Slug:** `produce-the-offline-gmp-lot-release-integrity-attestation-ar`
- **Category:** security
- **Difficulty:** hard

## Summary

Produce the offline GMP lot-release integrity attestation artifacts under /app for quality-unit and compliance reviewers. This is a regulated release-governance security review.

The security analysis reads the authoritative lot evidence dossier at /app/environment/metadata/base, materializes the normalized integrity staging capsule at /app/state/batch-release-snapshot.json, advances the release-authorization continuity ledger at /app/state/release-auth-ledger.json, and writes the paired trust attestation at /app/output/batch-release-audit.json. Security control contracts live in /app/docs/metadata-contract.md, /app/docs/qc-policy.md, /app/docs/equipment-policy.md, /app/docs/environmental-policy.md, /app/docs/documentation-policy.md, /app/docs/staging-snapshot.md, /app/docs/authorization-ledger.md, /app/docs/report-schema.md, and /app/docs/integrity-attestation-invocation.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
