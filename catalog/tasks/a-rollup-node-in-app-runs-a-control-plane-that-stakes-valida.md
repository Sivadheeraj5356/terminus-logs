# A rollup node in /app runs a control plane that stakes validators, finalizes L2 

Submission: `601a658d-baf5-43df-ba90-de1be362db1a`  
Slug: `a-rollup-node-in-app-runs-a-control-plane-that-stakes-valida`  
Latest archive: `601a658d-baf5-43df-ba90-de1be362db1a_submission_2026-07-18T07_12_52.216Z.zip`  
Revisions: 1

## Task summary

A rollup node in /app runs a control plane that stakes validators, finalizes L2 blocks by weighted committee endorsement, bridges L1 deposits into L2 balances, and runs governance referenda with re-delegable ballots. Some safeguards no longer hold. Probe the service as an attacker would; confirm each property and correct any that fails. A bridged deposit becomes an irreversible L2 credit only once it sits the configured confirmation depth under the L1 tip — not a block early, nor withheld once that deep. An applied deposit credits the account it names as recipient, not the operator that relayed it. A re-delegated ballot votes only while the account that shared it still holds the referendum. Operational statistics stay shut to a plain participant. A failed login never betrays whether the username exists. A validator joins the active set only when its integrity attestation verifies. No signing key or settlement credential appears in a response, and none of these — nor a session credential — is ever written to /app/audit.log. One network's validators stay invisible to accounts in another.

Required artifacts include: `/app/audit.log`, `/app/docs/api.md`.

Author anonymous tagged this **medium** security task (security, rust, blockchain, rollup, bridge, consensus).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `601a658d-baf5-43df-ba90-de1be362db1a_submission_2026-07-18T07_12_52.216Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
