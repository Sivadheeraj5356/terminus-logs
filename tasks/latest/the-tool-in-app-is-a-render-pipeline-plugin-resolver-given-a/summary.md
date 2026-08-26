# The tool in `/app` is a render-pipeline plugin resolver: given a plugin registry

- **UUID:** `4554bd77-d136-4604-95e3-97865aa90c5c`
- **Slug:** `the-tool-in-app-is-a-render-pipeline-plugin-resolver-given-a`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The tool in `/app` is a render-pipeline plugin resolver: given a plugin registry and a set of top-level requirements, it computes the install set (the single version chosen for every plugin that must be installed) together with any conflict records for dependencies that cannot be satisfied. The starter at `/app/main.cpp` only resolves the top-level requirements with a naive reading of a few operators and never follows the dependency constraints declared between plugins; extend it so that for every case its result matches the resolution contract described in the project `/app/README.md`.

The program reads one JSON array of resolution cases from standard input and writes one JSON array of results to standard output, one per case in the same order; an empty input array must produce an empty output array. Each case names a `registry`, mapping every plugin to its available versions (each with its optional `yanked` flag and its `deps` constraints on other plugins), and a `requirements` map of the top-level constraints, and its result is an object with an `install` array of `{name, version}` entries sorted by plugin name and a `conflicts` array of `{packages, dependency}` records.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
