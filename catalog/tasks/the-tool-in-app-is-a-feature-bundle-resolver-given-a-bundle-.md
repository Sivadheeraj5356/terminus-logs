# The tool in `/app` is a feature-bundle resolver: given a bundle registry and a

Submission: `1a641bea-ecda-4a86-8617-327929683da0`  
Slug: `the-tool-in-app-is-a-feature-bundle-resolver-given-a-bundle-`  
Latest archive: `1a641bea-ecda-4a86-8617-327929683da0_submission_2026-07-17T06_08_43.150Z.zip`  
Revisions in Dropbox: 2

## Task summary

The tool in `/app` is a feature-bundle resolver: given a bundle registry and a set of top-level requirements, it computes the install set, the single version chosen for every bundle that must be installed, together with any conflict records for dependencies that cannot be satisfied. The starter at `/app/Main.java` only resolves the top-level requirements with a naive reading of a few operators and never follows the dependency constraints that one bundle version declares on another. Extend it so that for every case its result matches the resolution contract described in the project `/app/README.md`. The program reads one JSON array of resolution cases from standard input and writes one JSON array of results to standard output, one per case in the same order; an empty input array must produce an empty output array. Each case names a `registry`, mapping every bundle to its available versions (each with its optional `yanked` flag and its `deps` constraints on other bundles), and a `requirements` map of the top-level constraints, and its result is an object with an `install` array of `{name, version}` entries sorted by bundle name and a `conflicts` array of `{packages, dependency}` records. The `/app/README.md` is the authoritative description of the version precedence, the constraint operators and their expansions, the highest-version selection, the pre-release and yanked admissibility rules, transitive constraint activation, and the deterministic conflict records; `/app/sample_inputs.json` holds `{registry, requirements}` example inputs you can resolve to check your work.

Required artifacts include: `/app/Main.java`, `/app/README.md`, `/app/sample_inputs.json`.

Author anonymous tagged this **hard** build-and-dependency-management task (dependency-resolution, semver, version-constraints, install-set, bundle-registry).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `1a641bea-ecda-4a86-8617-327929683da0_submission_2026-07-17T06_08_43.150Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
