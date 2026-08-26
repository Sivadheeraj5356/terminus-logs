# Our Rust microservice release build links cleanly but panics in production when 

Submission: `05568c77-ec21-4c74-967e-504baaed893d`  
Slug: `our-rust-microservice-release-build-links-cleanly-but-panics`  
Latest archive: `05568c77-ec21-4c74-967e-504baaed893d_submission_2026-07-07T19_32_19.550Z.zip`  
Revisions: 2

## Task summary

Our Rust microservice release build links cleanly but panics in production when serde json serialization runs. Local dev builds behave fine. Cargo feature unification across the workspace graph is dropping required crate features in release. Repair the Go feature reconciler under `/app/featurectl` and `/app/cargograph` only. Go 1.24 is preinstalled at `/usr/local/go/bin` on PATH. From `/app` run `make build` then `make run` offline without apt install. `make build` must produce `/app/build/featrecon` only. `make run` writes `/app/build/feature_resolution_report.json`.

Required artifacts include: `/app/featurectl`, `/app/cargograph`, `/app/build/featrecon`, `/app/build/feature_resolution_report.json`, `/app/feature-policy/rules_index.json`, `/app/feature-policy`, `/app/crate-captures`, `/app/crate-captures/.capture_guard`.

Author anonymous tagged this **hard** build-and-dependency-management task (cargo, feature-flags, workspace, dependency-graph, rust, go).

Time estimates: expert ~180.0 min, junior ~360.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `05568c77-ec21-4c74-967e-504baaed893d_submission_2026-07-07T19_32_19.550Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
