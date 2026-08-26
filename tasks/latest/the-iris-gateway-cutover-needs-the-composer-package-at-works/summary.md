# The Iris gateway cutover needs the Composer package at /workspace/iris-provenanc

- **UUID:** `5b1a670c-a989-4f9d-ae60-eeff3a2a466f`
- **Slug:** `the-iris-gateway-cutover-needs-the-composer-package-at-works`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The Iris gateway cutover needs the Composer package at /workspace/iris-provenance to resolve Go module conflict policy for require vs replace, retract, excludes, and scaffolding flags. The package already contains a draft walker and digest exporter — repair them so Composer/Phinx can publish a build-ready module graph, land it into the dependency database named by the active paths file, and pin a checksummed lock digest the release gate can verify.

Path bindings live in /workspace/config/paths.json. Use proxy_export and cutover_register from that file (other path keys are historical or smoke mirrors).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
