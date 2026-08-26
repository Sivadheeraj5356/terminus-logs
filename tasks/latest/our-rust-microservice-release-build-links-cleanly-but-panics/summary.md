# Our Rust microservice release build links cleanly but panics in production when

- **UUID:** `05568c77-ec21-4c74-967e-504baaed893d`
- **Slug:** `our-rust-microservice-release-build-links-cleanly-but-panics`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Our Rust microservice release build links cleanly but panics in production when serde json serialization runs. Local dev builds behave fine.

Cargo feature unification across the workspace graph is dropping required crate features in release. Repair the Go feature reconciler under `/app/featurectl` and `/app/cargograph` only.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
