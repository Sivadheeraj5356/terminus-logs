# A Go parcel access-control gateway lives under /app/environment. It reads untrus

Submission: `90f2a905-eb44-4c77-9805-2ed92f74162a`  
Slug: `a-go-parcel-access-control-gateway-lives-under-app-environme`  
Latest archive: `90f2a905-eb44-4c77-9805-2ed92f74162a_submission_2026-07-18T14_12_46.655Z.zip`  
Revisions in Dropbox: 2

## Task summary

A Go parcel access-control gateway lives under /app/environment. It reads untrusted parcel-routing scripts and must emit exact allow or deny security decisions for each valid request record. Bring the gateway into conformance with the security contract in /app/environment/docs/ACCESS_CONTRACT.md. The contract covers field-count validation, ignored malformed records, generated route policies, checkpoints, replay behavior, overlays, seals, leases, rates, budgets, TTL aging, sequenced request-id binding, and rollback after denials. Standard output must contain exactly one decision line for each valid REQ record and no output for state records or ignored records.

Required artifacts include: `/app/environment`, `/app/environment/docs/ACCESS_CONTRACT.md`, `/app/environment/testdata/happy.script`.

Author anonymous tagged this **unknown** security task (authorization, access-control, replay-protection, rate-limiting, cwe-284, cwe-863).

Time estimates: expert ~480 min, junior ~1200 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `90f2a905-eb44-4c77-9805-2ed92f74162a_submission_2026-07-18T14_12_46.655Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
