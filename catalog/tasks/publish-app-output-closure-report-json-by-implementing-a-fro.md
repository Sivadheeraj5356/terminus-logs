# Publish `/app/output/closure_report.json` by implementing a from-scratch Go clos

Submission: `8a1488a8-3662-4734-b3bf-c27d44be6dda`  
Slug: `publish-app-output-closure-report-json-by-implementing-a-fro`  
Latest archive: `8a1488a8-3662-4734-b3bf-c27d44be6dda_submission_2026-07-16T16_55_11.987Z.zip`  
Revisions in Dropbox: 1

## Task summary

Publish `/app/output/closure_report.json` by implementing a from-scratch Go closure merge engine, building `/app/bin/cl_publish` through `/app/scripts/compile_report.sh` or `/app/launcher/cl_publish`. The image ships tenant fragments, registry rows, runtime defaults, and consolidation docs under `/app/doc/` but no Go implementation sources. Each publish must reload `/app/cfg/runtime.toml` and `/app/data/tenant_registry.json` from disk with no cross-run caching, including consecutive in-process invocations and tenants appended mid-session.

Required artifacts include: `/app/output/closure_report.json`, `/app/bin/cl_publish`, `/app/scripts/compile_report.sh`, `/app/launcher/cl_publish`, `/app/doc/`, `/app/cfg/runtime.toml`, `/app/data/tenant_registry.json`, `/app/stubs/revision_stamp.txt`.

Author anonymous tagged this **hard** data-processing task (config-merge, overlay, patch-semantics, go, closure, fragments).

Time estimates: expert ~240 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8a1488a8-3662-4734-b3bf-c27d44be6dda_submission_2026-07-16T16_55_11.987Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
