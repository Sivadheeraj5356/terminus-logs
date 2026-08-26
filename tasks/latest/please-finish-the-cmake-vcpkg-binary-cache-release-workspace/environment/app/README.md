# ReleaseKit workspace

This Rust-only workspace packages the offline CMake/vcpkg binary cache release. Running `/app/scripts/release.sh` must build the `releasekit` binary with Cargo locked and offline, remove stale `/app/dist` contents, and create one unpacked bundle plus one reproducible tarball for every row in `config/release_matrix.csv`.

Read `docs/vcpkg-release-contract.md` as the authoritative artifact contract, the compact normative `docs/advanced-graph-contract.md` for SCC ordering and edge multiplicity, `docs/policy-contract.md` for audit and warning rules, and `docs/data-dictionary.md` for the CSV fields. The checked-in manifests, CSVs, and smoke files are examples rather than a fixed release inventory.

Every bundle copies the complete current `config/release_matrix.csv` verbatim; unlike the component, lock, and dependency CSVs, the matrix is never profile-filtered. Every tarball starts with the explicit `releasekit-<profile>` directory member itself.

Every bundle copies the complete current matrix verbatim, while the component, lock, and dependency files follow their documented profile filters. All output schemas, graph rules, metadata resolution, and relocation requirements are defined in the contracts above.
