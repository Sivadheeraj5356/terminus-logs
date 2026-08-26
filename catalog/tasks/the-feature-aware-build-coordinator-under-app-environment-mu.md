# The feature-aware build coordinator under `/app/environment` must certify that e

Submission: `32e9eda8-d2a3-4e2d-9874-bd8335c3e03b`  
Slug: `the-feature-aware-build-coordinator-under-app-environment-mu`  
Latest archive: `32e9eda8-d2a3-4e2d-9874-bd8335c3e03b_submission_2026-07-11T03_09_31.373Z.zip`  
Revisions: 6

## Task summary

The feature-aware build coordinator under `/app/environment` must certify that every expanded task graph stays acyclic across flag combinations. Primary arms in `/app/environment/docs/primary_flags.txt` look sound after `bash /app/environment/scripts/bp_run`, but held-out rows from `/app/environment/data/extra_flags.toml` show stuck counters or non-zero lag. Echo pairs disagree on facet material, witness sidecars under `/app/output/witness_meta/` disagree with the JSON certificate, and the status probe can read steady while the report is incoherent.

Required artifacts include: `/app/environment`, `/app/environment/docs/primary_flags.txt`, `/app/environment/scripts/bp_run`, `/app/environment/data/extra_flags.toml`, `/app/output/witness_meta/`, `/app/output/cert_report.json`, `/app/output/run_traces/`, `/app/environment/state/k3_ledger.tsv`.

Author anonymous tagged this **hard** build-and-dependency-management task (typescript, build-graph, feature-flags, dag-proof, witness, offline-build).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `32e9eda8-d2a3-4e2d-9874-bd8335c3e03b_submission_2026-07-11T03_09_31.373Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
