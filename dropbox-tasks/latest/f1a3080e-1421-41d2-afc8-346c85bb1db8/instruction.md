The Vellum monorepo in `/app` ships a cryptographic document engine as a native library, a Python wheel, and a Node package for air-gapped qualification. The developer entry points `/app/scripts/dev-build` and `/app/scripts/dev-check` pass, but the release does not hold together.

Running `/app/scripts/release --source-root <abs> --output <abs>` must write a complete bundle that satisfies `/app/docs/release-contract.md`. With the default output root the bundle lives at `/output/release` and contains the native library `/output/release/native/libvellum.so`, an installable Python wheel under `/output/release/python/`, an installable Node tarball under `/output/release/node/`, the dependency inventory `/output/release/metadata/dependency-inventory.json`, the signed provenance manifest `/output/release/metadata/provenance.json`, and the checksum manifest `/output/release/SHA256SUMS`.

Today the release is broken in several ways:

- Clean releases from different absolute source roots produce different bytes, so `/output/release/SHA256SUMS` is not reproducible.
- The Python wheel and Node package disagree with the native library on release identity: the `release_id`, `abi_fingerprint`, `capabilities`, and dependency-closure digest differ, and the surfaces compute different canonical digests for some documents and cannot all perform the operations they advertise.
- The `components` and `closure_digest` in `/output/release/metadata/dependency-inventory.json` do not describe the closure actually compiled into the shipped native library.
- The `subjects`, `release_id`, and `abi_fingerprint` recorded in `/output/release/metadata/provenance.json` do not match the final shipped bytes.

Fix the source under `/app` so that, for identical inputs, `/app/scripts/release --source-root <abs> --output <abs>` is byte-for-byte reproducible across different roots and harmless host-environment differences; all three surfaces report one identity and agree on the documented operations; `/output/release/metadata/dependency-inventory.json` matches the closure actually compiled; and `/output/release/metadata/provenance.json` binds the final artifacts with a signature that verifies against the shipped public key. The build must stay offline and self-contained after install.

The verifier runs `/app/scripts/release` itself and inspects the regenerated bundle, so hand-editing or pre-staging files under `/output` is not sufficient; the fix must live in `/app`. Treat `/app/docs`, `/app/interface`, `/app/config`, `/app/VERSION`, `/app/REVISION`, `/app/policy`, `/app/fixtures`, `/app/vendor`, and the checked-in lockfiles as immutable inputs, and keep `/app/scripts/dev-build` and `/app/scripts/dev-check` working.
