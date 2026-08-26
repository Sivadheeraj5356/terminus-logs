# Repair `/app/bin/mediate-deps` so it mediates the offline bundle in `/app/data` 

Submission: `1fe5cff0-5933-4d47-8274-1dfc9e9f8211`  
Slug: `repair-app-bin-mediate-deps-so-it-mediates-the-offline-bundl`  
Latest archive: `1fe5cff0-5933-4d47-8274-1dfc9e9f8211_submission_2026-07-11T16_37_19.249Z.zip`  
Revisions in Dropbox: 1

## Task summary

Repair `/app/bin/mediate-deps` so it mediates the offline bundle in `/app/data` and writes `audit.json`, `classpath.csv`, `mediation.csv`, and `findings.csv` as documented in `/app/README.md`. Use only local files under `/app`; no network access. The Clojure engine in `/app/src/indigo/` resolves the default bundle but does not fully implement every rule in `/app/mediation-policy.md`. Validate against both `/app/data` and the focused bundles under `/app/examples/` (including `nearest-tie/` and `topo-order/`); a zero-exit run on `/app/data` alone is not sufficient.

Required artifacts include: `/app/bin/mediate-deps`, `/app/data`, `/app/README.md`, `/app/src/indigo/`, `/app/mediation-policy.md`, `/app/examples/`, `/app/schemas/inputs.schema.md`, `/app/schemas`.

Author anonymous tagged this **hard** build-and-dependency-management task (clojure, maven, dependencies, mediation, offline).

Time estimates: expert ~120 min, junior ~180 min.

Harbor timeouts: agent 1200.0s, verifier 420.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `1fe5cff0-5933-4d47-8274-1dfc9e9f8211_submission_2026-07-11T16_37_19.249Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
