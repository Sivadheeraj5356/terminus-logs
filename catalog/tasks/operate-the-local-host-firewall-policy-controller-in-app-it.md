# Operate the local host firewall policy controller in `/app`. It does not converg

Submission: `5d25f049-36d8-444d-9950-92ca6a6eb5a8`  
Slug: `operate-the-local-host-firewall-policy-controller-in-app-it`  
Latest archive: `5d25f049-36d8-444d-9950-92ca6a6eb5a8_submission_2026-07-19T17_03_07.622Z.zip`  
Revisions: 4

## Task summary

Operate the local host firewall policy controller in `/app`. It does not converge after an interrupted apply, conflicting configuration drop-ins, or a restart with active runtime overrides. Operators rely on `nxctl apply` and `nxctl recover` to reconcile durable controller state with the effective host policy and ownership model documented under `/app/docs`. Administrative convergence must satisfy layered configuration precedence, counter lineage across chain regeneration, crash recovery after partial staging, preservation of foreign operator rules, validation that rejects invalid effective policy without mutating durable state, accurate `nxctl status --json` reporting, and upgrade of supported legacy ownership manifests. The controller must regenerate backend, manifest, and audit state through the normal apply and recover workflow; direct edits to durable state files or verifier-only artifacts are insufficient.

Required artifacts include: `/app/docs`, `/app/state/backend.json`, `/app/state/ownership-manifest.json`, `/app/state/runtime-overrides.json`, `/app/state/audit.jsonl`, `/app/docs/cli-contract.md`, `/app/docs/configuration-precedence.md`, `/app/docs/reconciliation-contract.md`.

Author anonymous tagged this **hard** system-administration task (firewall, host-policy, network-policy, daemon-administration, services, reconciliation, nftables, crash-recovery, configuration-precedence, counter-lineage).

Time estimates: expert ~210 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `5d25f049-36d8-444d-9950-92ca6a6eb5a8_submission_2026-07-19T17_03_07.622Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
