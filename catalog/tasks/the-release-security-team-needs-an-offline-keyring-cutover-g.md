# The release security team needs an offline keyring cutover gate for one verifier

Submission: `7f868c3e-bc97-4019-8745-5c03499d1340`  
Slug: `the-release-security-team-needs-an-offline-keyring-cutover-g`  
Latest archive: `7f868c3e-bc97-4019-8745-5c03499d1340_submission_2026-07-17T11_04_40.528Z.zip`  
Revisions in Dropbox: 3

## Task summary

The release security team needs an offline keyring cutover gate for one verifier image. The staged inputs describe candidate trust bundles, issuer limits, revoked issuers, and the claims that must be preserved during the cutover. Write `/app/keyring_cutover_gate.go`, build `/app/keyring_cutover_gate`, and run it as `/app/keyring_cutover_gate /app/input_data/request.json /app/input_data/catalog.json /app/output_data/cutover_plan.json` without modifying the inputs. Key requirements: Maximize the number of satisfied rows in `request.required_claims`.; Minimize total selected `risk`.; Minimize total selected `footprint_kb`.; Minimize the number of selected bundles..

Required artifacts include: `/app/keyring_cutover_gate.go`, `/app/keyring_cutover_gate`, `/app/input_data/request.json`, `/app/input_data/catalog.json`, `/app/output_data/cutover_plan.json`, `/app/keyring_cutover_contract.md`.

Author Anonymous tagged this **hard** security task (go, security, trust-bundle, keyring-rotation, policy-gate, offline-verification).

Time estimates: expert ~180.0 min, junior ~780.0 min.

Harbor timeouts: agent 1200.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `7f868c3e-bc97-4019-8745-5c03499d1340_submission_2026-07-17T11_04_40.528Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
