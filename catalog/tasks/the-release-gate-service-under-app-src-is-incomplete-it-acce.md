# The release-gate service under `/app/src/` is incomplete. It accepts evaluation 

Submission: `29944a6c-ea19-4149-8e92-c3d79349152f`  
Slug: `the-release-gate-service-under-app-src-is-incomplete-it-acce`  
Latest archive: `29944a6c-ea19-4149-8e92-c3d79349152f_submission_2026-07-15T08_54_40.842Z.zip`  
Revisions in Dropbox: 1

## Task summary

The release-gate service under `/app/src/` is incomplete. It accepts evaluation requests over HTTP and is supposed to decide whether a signed Git release tag is eligible for promotion, but currently approves everything. Fix the implementation so it correctly enforces the policy. The sole authority for policy behavior is `/app/standard/cdss_v4.md`. All decisions — how the compose model is assembled, how services are classified and evaluated, how policy obligations apply, how exception windows are consulted, and how key and hook requirements are verified — follow that document. The HTTP wire contract (endpoint definitions, request/response structure, and the database connection requirement) is in `/app/docs/api_contract.md`.

Required artifacts include: `/app/src/`, `/app/standard/cdss_v4.md`, `/app/docs/api_contract.md`, `/app/build.sh`, `/app/bin/gate.jar`, `/app/scripts/run_gate.sh`, `/app/data/approvals.mv.db`, `/app/data/seed_approvals.sql`.

Author anonymous tagged this **hard** security task (docker-compose, h2-database, gpg-signed-tags, policy-engine, release-gating).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `29944a6c-ea19-4149-8e92-c3d79349152f_submission_2026-07-15T08_54_40.842Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through. Git history or refs are only partially repaired.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
