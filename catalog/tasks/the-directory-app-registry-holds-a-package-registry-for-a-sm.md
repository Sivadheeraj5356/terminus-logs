# The directory /app/registry holds a package registry for a small dependency ecos

Submission: `2710e65c-f91e-477d-8251-9c0ccbf7ddba`  
Slug: `the-directory-app-registry-holds-a-package-registry-for-a-sm`  
Latest archive: `2710e65c-f91e-477d-8251-9c0ccbf7ddba_submission_2026-07-16T20_45_11.058Z.zip`  
Revisions in Dropbox: 1

## Task summary

The directory /app/registry holds a package registry for a small dependency ecosystem, dozens of packages each with one or more released versions, each version declaring what it requires and what it conflicts with. /app/manifest.toml lists the root requirements for the application under /app/project. Resolve a set of package versions that satisfies every requirement and conflict for this manifest, the way /app/RULES.md defines satisfaction, and write it to /app/out/lock.json in the shape that contract specifies. /app/project already has a fixed consumer.go that imports fleetmesh/compat/telemetrybusv1, a package that does not exist yet. Whatever telemetrybus version your resolution settles on, consumer.go needs that import path to provide a working implementation backed by it. The registry documents each version's public surface, and any version that changed that surface carries a MIGRATION.md next to its stub describing what changed. Write the compat package under /app/project/compat/telemetrybusv1/ so that go build ./... from /app/project succeeds and behaves the way consumer.go and the resolved telemetrybus version expect together.

Required artifacts include: `/app/registry`, `/app/manifest.toml`, `/app/project`, `/app/RULES.md`, `/app/out/lock.json`, `/app/project/compat/telemetrybusv1/`, `/app/project/resolver/main.go`.

Author anonymous tagged this **unknown** build-and-dependency-management task (dependency-resolution, package-registry, sat-solving, api-migration, compatibility-shim, go).

Time estimates: expert ~210 min, junior ~450 min.

Harbor timeouts: agent 1800.0s, verifier 400.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `2710e65c-f91e-477d-8251-9c0ccbf7ddba_submission_2026-07-16T20_45_11.058Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
