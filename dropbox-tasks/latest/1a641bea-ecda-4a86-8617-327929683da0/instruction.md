The tool in `/app` is a feature-bundle resolver: given a bundle registry and a
set of top-level requirements, it computes the install set, the single version
chosen for every bundle that must be installed, together with any conflict
records for dependencies that cannot be satisfied. The starter at `/app/Main.java`
only resolves the top-level requirements with a naive reading of a few operators
and never follows the dependency constraints that one bundle version declares on
another. Extend it so that for every case its result matches the resolution
contract described in the project `/app/README.md`.

The program reads one JSON array of resolution cases from standard input and
writes one JSON array of results to standard output, one per case in the same
order; an empty input array must produce an empty output array. Each case names a
`registry`, mapping every bundle to its available versions (each with its
optional `yanked` flag and its `deps` constraints on other bundles), and a
`requirements` map of the top-level constraints, and its result is an object with
an `install` array of `{name, version}` entries sorted by bundle name and a
`conflicts` array of `{packages, dependency}` records. The `/app/README.md` is the
authoritative description of the version precedence, the constraint operators and
their expansions, the highest-version selection, the pre-release and yanked
admissibility rules, transitive constraint activation, and the deterministic
conflict records; `/app/sample_inputs.json` holds `{registry, requirements}` example
inputs you can resolve to check your work.
