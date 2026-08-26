# The Vellum monorepo in `/app` ships a cryptographic document engine as a native

- **UUID:** `f1a3080e-1421-41d2-afc8-346c85bb1db8`
- **Slug:** `the-vellum-monorepo-in-app-ships-a-cryptographic-document-en`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The Vellum monorepo in `/app` ships a cryptographic document engine as a native library, a Python wheel, and a Node package for air-gapped qualification. The developer entry points `/app/scripts/dev-build` and `/app/scripts/dev-check` pass, but the release does not hold together.

Running `/app/scripts/release --source-root <abs> --output <abs>` must write a complete bundle that satisfies `/app/docs/release-contract.md`. With the default output root the bundle lives at `/output/release` and contains the native library `/output/release/native/libvellum.so`, an installable Python wheel under `/output/release/python/`, an installable Node tarball under `/output/release/node/`, the dependency inventory `/output/release/metadata/dependency-inventory.json`, the signed provenance manifest `/output/release/metadata/provenance.json`, and the checksum manifest `/output/release/SHA256SUMS`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
