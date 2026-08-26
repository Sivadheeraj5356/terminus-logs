# A build-farm plugin compatibility checker receives exactly two command-line

Submission: `86dbf33c-b3c6-40b0-b98a-9b94c248f08f`  
Slug: `a-build-farm-plugin-compatibility-checker-receives-exactly-t`  
Latest archive: `86dbf33c-b3c6-40b0-b98a-9b94c248f08f_submission_2026-07-10T08_49_48.011Z.zip`  
Revisions: 2

## Task summary

A build-farm plugin compatibility checker receives exactly two command-line arguments: a candidate dependency version and a requested version selector, both written as text. For that pair, it must print exactly one line, either `true` or `false` followed by a newline, reporting whether the candidate version is admitted by the selector. The behavior you must reproduce is Gradle's dependency version selection: given a single candidate version and a version selector, decide whether Gradle would consider that version to match the selector. Treat Gradle's own matching as the definition of correct behavior and match it exactly, for every version and selector pair. This covers Gradle's static-version comparison (how a version string is split into parts and how those parts are ordered), the special ordering of qualifier words such as `dev`, `rc`, `snapshot`, `final`, `ga`, `release` and `sp` (and how unrecognized qualifiers order among themselves), the comparison of numeric against non-numeric parts, and the tie-breaking between versions of unequal length.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** build-and-dependency-management task (kotlin, gradle, version-selector, version-constraint, differential, dependency-management).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `86dbf33c-b3c6-40b0-b98a-9b94c248f08f_submission_2026-07-10T08_49_48.011Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
