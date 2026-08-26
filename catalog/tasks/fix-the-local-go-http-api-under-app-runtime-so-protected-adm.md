# Fix the local Go HTTP API under `/app/runtime` so protected admin endpoints requ

Submission: `60daaed1-f2f7-4b33-bc95-7bbbb3ea0896`  
Slug: `fix-the-local-go-http-api-under-app-runtime-so-protected-adm`  
Latest archive: `60daaed1-f2f7-4b33-bc95-7bbbb3ea0896_submission_2026-07-09T10_33_04.607Z.zip`  
Revisions in Dropbox: 1

## Task summary

Fix the local Go HTTP API under `/app/runtime` so protected admin endpoints require a valid bearer token on every request, including normalized/encoded path variants, replay probes, and restart/recovery sequences. Build and run with the Go toolchain at `/usr/local/go/bin`. The public routes are `GET /v1/public/ping`, `GET /v1/public/docs`, and `GET /v1/public/state` — these must stay available without authentication under all conditions. The ping endpoint returns `{"status":"ok"}`. The docs endpoint returns a JSON object with a `docs` field that lists the available protected routes including `/v1/admin/profile`. Protected routes are `/v1/admin/profile` and `/v1/admin/audit`. When a protected route is accessed without a valid bearer token or with an invalid one, the response must be status 401 with body `{"error":{"code":"unauthorized","message":"missing or invalid bearer token"}}`. Method-not-allowed and not-found error envelopes must also remain stable.

Required artifacts include: `/app/runtime`.

Author anonymous tagged this **hard** security task (auth, path-normalization, http, routing, security).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `60daaed1-f2f7-4b33-bc95-7bbbb3ea0896_submission_2026-07-09T10_33_04.607Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
