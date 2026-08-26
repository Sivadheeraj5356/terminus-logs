# Shared-port TLS challenge renewal completes on the direct office path while the 

Submission: `276b23cf-80b5-47b8-a809-65710df50e49`  
Slug: `shared-port-tls-challenge-renewal-completes-on-the-direct-of`  
Latest archive: `276b23cf-80b5-47b8-a809-65710df50e49_submission_2026-07-10T11_22_02.122Z.zip`  
Revisions in Dropbox: 1

## Task summary

Shared-port TLS challenge renewal completes on the direct office path while the proxied vantage still reports mismatched ALPN negotiation and certificate material for the same hostname. Authoritative DNS validation and HTTP-01 remain disabled by policy; only the remaining challenge type may be used. Fix sources under `/app/environment` so `/app/bin/run_lab` regenerates `/app/output/lab_observations.json` through the normal Rust pathlab driver. Static or hand-written observation JSON will not pass. Table-driven rules and manifests under `/app/environment/data/` govern compile preimage, route-plan caching, lane simulation, remote epoch binding, ALPN selection, seal encoding, and journal commit. Output schema and artifact paths are in `/app/environment/docs/field_contract.md`.

Required artifacts include: `/app/environment`, `/app/bin/run_lab`, `/app/output/lab_observations.json`, `/app/environment/data/`, `/app/environment/docs/field_contract.md`, `/app/var/`.

Author anonymous tagged this **hard** security task (acme, tls, alpn, certificate, validation).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `276b23cf-80b5-47b8-a809-65710df50e49_submission_2026-07-10T11_22_02.122Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
