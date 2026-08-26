# Now make the buildlist subcommand work. Given a registry directory and a main

- **UUID:** `f1c70a05-4e2d-4085-91c9-6c9bed3cee27`
- **Slug:** `now-make-the-buildlist-subcommand-work-given-a-registry-dire`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Now make the buildlist subcommand work. Given a registry directory and a main module manifest, it computes the build list, the map from each module reached in the transitive graph to its selected version, and writes it as the JSON in /app/app/docs/CLI.md.

The walk starts from the main module and reads a module version's manifest only at the moment it first needs it, following require directives outward until no new module version is reached. Manifests the walk never reaches are never read.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
