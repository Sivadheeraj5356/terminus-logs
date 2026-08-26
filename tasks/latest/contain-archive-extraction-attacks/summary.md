# # Contain archive extraction attacks

- **UUID:** `ddaf8052-e913-4c1a-a68d-180a40b3cad6`
- **Slug:** `contain-archive-extraction-attacks`
- **Category:** security
- **Difficulty:** hard

## Summary

An incident-response quarantine service received hostile nested submissions that escaped review roots, spoofed trusted paths, and exhausted workers. Harden the archive security boundary implemented under `/app/src` so it enforces the complete extraction security contract in `/app/docs/EXTRACTION_SECURITY.md`.

Keep the documented two-argument CLI. The hardened extractor must safely handle the documented TAR and ZIP inputs, recursively expand content-identified nested archives, preserve documented safe files and in-tree links, and enforce every path, entry-type, Unicode-collision, sparse-file, nesting, size, compression-ratio, and aggregate containment limit in the contract.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
