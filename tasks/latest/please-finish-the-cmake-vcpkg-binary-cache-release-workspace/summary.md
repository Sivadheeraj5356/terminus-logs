# Please finish the CMake/vcpkg binary-cache release workspace in `/app`. Keep it

- **UUID:** `b04f54f7-6743-4105-9700-131fdf99731d`
- **Slug:** `please-finish-the-cmake-vcpkg-binary-cache-release-workspace`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Please finish the CMake/vcpkg binary-cache release workspace in `/app`. Keep it fully offline: `/app/scripts/release.sh` and the `releasekit` binary must rebuild `/app/dist` from the current matrix, catalog, lock, dependency, and smoke inputs and produce the deterministic bundles, archives, manifest, checksums, and audit output defined in `/app/docs/vcpkg-release-contract.md`, `/app/docs/advanced-graph-contract.md`, `/app/docs/policy-contract.md`, and `/app/docs/data-dictionary.md`.

Every bundled `bin/releasekit` must be the compiled Linux ELF produced by the locked Cargo release build, not a script or proxy. All configuration and smoke inputs are live release inputs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
