# Repair the offline Go module policy-lock sources under /app so resolution stays 

Submission: `71fe619a-7cfa-437a-99d4-5c62cd96be62`  
Slug: `repair-the-offline-go-module-policy-lock-sources-under-app-s`  
Latest archive: `71fe619a-7cfa-437a-99d4-5c62cd96be62_submission_2026-07-19T17_59_14.054Z.zip`  
Revisions: 3

## Task summary

Repair the offline Go module policy-lock sources under /app so resolution stays consistent for clean copied roots, the offline mirror at /app/var/module-mirror/, workspace overlays, platform targets (GOOS/GOARCH), and interrupted policy-index updates. In-tree smoke runs can look fine. Copied roots, cross-platform runs, directive conflicts, legacy lock migrations, and resumed policy-db refresh runs show mismatched lockfiles, policy reports, or stale pin decisions. Rebuild with the workflow in /app/docs/BUILD.md; hand-written final artifacts are insufficient. Drive scenarios with /app/scripts/offline-modpolicy.sh and write /output/modpolicy.lock.json plus /output/policy-report.json. Success exits 0. Required artifact shapes are defined by /app/schemas/modpolicy.lock.schema.json and /app/schemas/policy-report.schema.json, including schema_version, goos, goarch, policy_revision, modules entries (path, version, source, policy_decision, replaces), and resolution_digest. Digest construction is defined in /app/docs/REPRO_DIGEST.md. For one request and platform pair, the lock and report must describe the same module graph (same selected versions, sources, and policy decisions).

Required artifacts include: `/app/var/module-mirror/`, `/app/docs/BUILD.md`, `/app/scripts/offline-modpolicy.sh`, `/output/modpolicy.lock.json`, `/output/policy-report.json`, `/app/schemas/modpolicy.lock.schema.json`, `/app/schemas/policy-report.schema.json`, `/app/docs/REPRO_DIGEST.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (go-modules, policy-lock, offline-mirror, sqlite-index, replace-directives, cache-identity).

Time estimates: expert ~200 min, junior ~780 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `71fe619a-7cfa-437a-99d4-5c62cd96be62_submission_2026-07-19T17_59_14.054Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
