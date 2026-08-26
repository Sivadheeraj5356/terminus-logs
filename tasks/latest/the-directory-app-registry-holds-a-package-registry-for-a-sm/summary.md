# The directory /app/registry holds a package registry for a small dependency ecos

- **UUID:** `2710e65c-f91e-477d-8251-9c0ccbf7ddba`
- **Slug:** `the-directory-app-registry-holds-a-package-registry-for-a-sm`
- **Category:** build-and-dependency-management
- **Difficulty:** unknown

## Summary

The directory /app/registry holds a package registry for a small dependency ecosystem, dozens of packages each with one or more released versions, each version declaring what it requires and what it conflicts with. /app/manifest.toml lists the root requirements for the application under /app/project.

Resolve a set of package versions that satisfies every requirement and conflict for this manifest, the way /app/RULES.md defines satisfaction, and write it to /app/out/lock.json in the shape that contract specifies. /app/project already has a fixed consumer.go that imports fleetmesh/compat/telemetrybusv1, a package that does not exist yet.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
