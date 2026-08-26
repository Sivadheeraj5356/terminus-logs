# A build-farm plugin compatibility checker receives exactly two command-line

- **UUID:** `86dbf33c-b3c6-40b0-b98a-9b94c248f08f`
- **Slug:** `a-build-farm-plugin-compatibility-checker-receives-exactly-t`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

A build-farm plugin compatibility checker receives exactly two command-line arguments: a candidate dependency version and a requested version selector, both written as text. For that pair, it must print exactly one line, either `true` or `false` followed by a newline, reporting whether the candidate version is admitted by the selector.

The behavior you must reproduce is Gradle's dependency version selection: given a single candidate version and a version selector, decide whether Gradle would consider that version to match the selector. Treat Gradle's own matching as the definition of correct behavior and match it exactly, for every version and selector pair.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
