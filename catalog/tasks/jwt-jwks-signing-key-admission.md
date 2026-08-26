# # JWT JWKS Signing-Key Admission

Submission: `cff50367-5b4b-48b3-8434-f580bb9a202d`  
Slug: `jwt-jwks-signing-key-admission`  
Latest archive: `cff50367-5b4b-48b3-8434-f580bb9a202d_submission_2026-07-14T12_37_09.302Z.zip`  
Revisions in Dropbox: 4

## Task summary

Security operators on JWT/JWKS trust boundaries enforce signing-key admission and revocation from local JWKS tier trees under `/app/environment/fixtures`. During ordinary rotate, retire, and peer-realm inherit work, a short local pulse probe can look fine while `/app/output/freshness-report.json` still admits withdrawn kids, lets weaker cache/tenant material override stronger issuer policy, drops inherited peer kids across the realm trust boundary, or leaves a stale rotation seal in force. Those are authorization failures: a retired signing kid must stay denied, stronger issuer policy must win, and foreign-realm residue must not cross the active profile principal. Implement JWT/JWKS signing-key admission controls under `/app/environment` from the authorization specification in `/app/environment/docs/contract.md` so `/app/bin/mux audit --profile <name>` regenerates `/app/output/freshness-report.json` through the normal admission path for the shipped `amber`, `beryl`, and `onyx` trust realms. Hand-written output is rejected. The verifier may delete that artifact and rerun the command. An advisory readiness probe is `/app/bin/mux pulse <name>`; it does not replace audit and must not be trusted over the admission path. `onyx` inherits shared keys from `beryl`, so beryl durable state must already exist when onyx is audited.

Required artifacts include: `/app/environment/fixtures`, `/app/output/freshness-report.json`, `/app/environment`, `/app/environment/docs/contract.md`, `/app/bin/mux`.

Author anonymous tagged this **hard** security task (jwt, jwks, security, key-revocation, signing-key-admission, trust-boundary).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `cff50367-5b4b-48b3-8434-f580bb9a202d_submission_2026-07-14T12_37_09.302Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
