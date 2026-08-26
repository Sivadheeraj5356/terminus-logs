# Our release builders need an offline lock resolver for registries whose releases

- **UUID:** `f19973d2-4637-4d9c-a00b-9dc5b09d59da`
- **Slug:** `our-release-builders-need-an-offline-lock-resolver-for-regis`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Our release builders need an offline lock resolver for registries whose releases can expose several ABI-tagged capabilities. Build it as a Rust native executable so the same resolver can be rerun for different targets and policy profiles.

Create /opt/linkseal/src/main.rs and compile /opt/linkseal/bin/linkseal as an ELF binary. The command is:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
