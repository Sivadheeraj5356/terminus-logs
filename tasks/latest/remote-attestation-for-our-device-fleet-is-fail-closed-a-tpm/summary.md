# Remote attestation for our device fleet is fail-closed: a TPM2 quote cartridge m

- **UUID:** `672694ec-c172-4fc4-a523-d3a64bf4e801`
- **Slug:** `remote-attestation-for-our-device-fleet-is-fail-closed-a-tpm`
- **Category:** security
- **Difficulty:** hard

## Summary

Remote attestation for our device fleet is fail-closed: a TPM2 quote cartridge must prove authenticity and measurement integrity before the device may be marked trusted. Reject forged ECDSA P-256 quotes, nonce replays, PCR digests that do not bind the event log, clock or counter rollback, unsafe clocks, disallowed firmware versions, and reference-measurement or event-order policy violations.

Accept only evidence that authenticates and also satisfies the published appraisal rules. Evidence cartridges live under `/app/data`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
