# Request admission security gate (`siggate`)

Submission: `5a15cc6d-691f-40c9-affa-cfb766041872`  
Slug: `request-admission-security-gate-siggate`  
Latest archive: `5a15cc6d-691f-40c9-affa-cfb766041872_submission_2026-07-21T04_42_37.123Z.zip`  
Revisions in Dropbox: 1

## Task summary

Request admission security gate (`siggate`) ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ This is a **perimeter authentication and anti-replay security control**. At request admission, `/app/bin/siggate` must reject **forged** Harbor Request MAC v1 (HRM-1) envelopes and **replayed** authentic envelopes before traffic is admitted. Admit/deny outcomes are security decisions under the site profile.

Required artifacts include: `/app/bin/siggate`, `/app/docs/`, `/app/docs/cli-surface.md`, `/app/docs/query.md`, `/app/docs/digest.md`, `/app/docs/time.md`, `/app/docs/profile.md`, `/app/data/site.profile`.

Author anonymous tagged this **hard** security task (hmac, replay, authentication, admission-control, anti-forgery, go).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5a15cc6d-691f-40c9-affa-cfb766041872_submission_2026-07-21T04_42_37.123Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
