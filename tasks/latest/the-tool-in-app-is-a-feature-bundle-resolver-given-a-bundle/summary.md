# The tool in `/app` is a feature-bundle resolver: given a bundle registry and a

- **UUID:** `1a641bea-ecda-4a86-8617-327929683da0`
- **Slug:** `the-tool-in-app-is-a-feature-bundle-resolver-given-a-bundle`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The tool in `/app` is a feature-bundle resolver: given a bundle registry and a set of top-level requirements, it computes the install set, the single version chosen for every bundle that must be installed, together with any conflict records for dependencies that cannot be satisfied. The starter at `/app/Main.java` only resolves the top-level requirements with a naive reading of a few operators and never follows the dependency constraints that one bundle version declares on another.

Extend it so that for every case its result matches the resolution contract described in the project `/app/README.md`. The program reads one JSON array of resolution cases from standard input and writes one JSON array of results to standard output, one per case in the same order; an empty input array must produce an empty output array.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
