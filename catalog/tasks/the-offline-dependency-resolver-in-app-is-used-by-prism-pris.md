# The offline dependency resolver in /app is used by prism prism release workers t

Submission: `df041e50-c298-4587-a3fe-75bea002b266`  
Slug: `the-offline-dependency-resolver-in-app-is-used-by-prism-pris`  
Latest archive: `df041e50-c298-4587-a3fe-75bea002b266_submission_2026-07-01T08_33_36.539Z.zip`  
Revisions in Dropbox: 1

## Task summary

The offline dependency resolver in /app is used by prism prism release workers to update a deterministic dependency forge lockfile from a workspace request file and an on-disk package registry. Repair the prism-dependency-forge CLI so it follows /app/docs/resolver-contract.md. It must resolve aliases, version constraints, yanked releases, transitive dependencies, and feature-driven dependencies without using the network. Successful runs write the deterministic dependency forge lockfile schema described in /app/docs/lock-schema.md; failed runs write a conflict report and must not modify any existing lockfile. This task is hard because the resolver has to keep several dependency-management rules true at the same time, not just parse a file and pick versions. A mostly working solution can still fail when aliases, transitive feature requests, yanked versions, and conflicting constraints interact. Humans tend to underestimate the reprocessing needed after a feature activates new dependencies, and agents of

Required artifacts include: `/app/docs/resolver-contract.md`, `/app/docs/lock-schema.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (rust, lockfile, dependency-resolution, semver, cli, offline).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1200.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `df041e50-c298-4587-a3fe-75bea002b266_submission_2026-07-01T08_33_36.539Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
