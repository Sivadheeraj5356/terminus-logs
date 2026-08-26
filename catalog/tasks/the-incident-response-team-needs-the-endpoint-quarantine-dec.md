# The incident-response team needs the endpoint quarantine decision gate in `/app`

Submission: `5e0e87a7-9e41-486d-ae19-81032b052d1e`  
Slug: `the-incident-response-team-needs-the-endpoint-quarantine-dec`  
Latest archive: `5e0e87a7-9e41-486d-ae19-81032b052d1e_submission_2026-07-20T05_43_04.995Z.zip`  
Revisions in Dropbox: 1

## Task summary

The incident-response team needs the endpoint quarantine decision gate in `/app` completed before the next SOAR drill. The gate reviews a proposed containment bundle, applies the quarantine approval policy, and emits the exact decision JSON imported by the response workflow. Implement the `/app/quarantine-plan` command in Go. The verifier builds it from the module already present in `/app` and invokes:

Required artifacts include: `/app/quarantine-plan`, `/app/containment/bundle.json`, `/app/containment/QUARANTINE_POLICY.md`.

Author Anonymous tagged this **hard** security task (security, incident-response, endpoint-quarantine, soar, containment, risk-scoring).

Time estimates: expert ~180.0 min, junior ~720.0 min.

Harbor timeouts: agent 1200.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5e0e87a7-9e41-486d-ae19-81032b052d1e_submission_2026-07-20T05_43_04.995Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
