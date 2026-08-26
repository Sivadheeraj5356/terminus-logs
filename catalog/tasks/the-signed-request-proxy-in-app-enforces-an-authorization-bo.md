# The signed-request proxy in `/app` enforces an authorization boundary between HM

Submission: `90013102-c160-4394-9385-a4968e9e9165`  
Slug: `the-signed-request-proxy-in-app-enforces-an-authorization-bo`  
Latest archive: `90013102-c160-4394-9385-a4968e9e9165_submission_2026-07-19T04_23_03.210Z.zip`  
Revisions in Dropbox: 2

## Task summary

The signed-request proxy in `/app` enforces an authorization boundary between HMAC verification and backend forwarding. `/app/bin/proxy-local` must authorize and forward the same semantic request for live traffic and for requests recovered from `/app/state/spool`. Align the implementation with the profiles and recovery rules in `/app/docs/request-semantics.md`: valid current and legacy signatures remain accepted, invalid or ambiguous requests are rejected before forwarding, and duplicate or connection-nominated headers, encoded paths and queries, transfer framing, body limits, key/profile epochs, rotation, revocation, and restart recovery produce the documented backend request and decision. Keep the existing local-only CLI and streaming limits. Every run must write `/output/request-trace.json` with schema_version, run_mode, catalog_digest, and entries. Each entry must include request_id, source, decision, canonical_digest, cache_hit, body_sha256, and audit_record_digest. Recovered requests must preserve the original decision-time signature, profile, key, body, forwarding, spool, and audit evidence. Do not bypass cryptographic verification, disable compatibility paths, or require network access. Treat `/app/docs`, `/app/config`, and `/app/data` as immutable contract and fixture assets.

Required artifacts include: `/app/bin/proxy-local`, `/app/state/spool`, `/app/docs/request-semantics.md`, `/output/request-trace.json`, `/app/docs`, `/app/config`, `/app/data`.

Author anonymous tagged this **hard** security task (request-signing, hmac-authorization, canonicalization, reverse-proxy, key-rotation, authority-boundary).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `90013102-c160-4394-9385-a4968e9e9165_submission_2026-07-19T04_23_03.210Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
