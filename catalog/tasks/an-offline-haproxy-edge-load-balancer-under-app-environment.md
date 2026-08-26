# An offline HAProxy edge load-balancer under `/app/environment` composes ACL and 

Submission: `0d35c7d1-a960-461c-ad58-1299f2e509cf`  
Slug: `an-offline-haproxy-edge-load-balancer-under-app-environment`  
Latest archive: `0d35c7d1-a960-461c-ad58-1299f2e509cf_submission_2026-07-18T06_22_32.046Z.zip`  
Revisions: 1

## Task summary

An offline HAProxy edge load-balancer under `/app/environment` composes ACL and backend route plans, commits them as immutable generations behind a plan/commit token workflow, and records every commit in an append-only hash-chained ledger. The pipeline has drifted out of the contract documented under `/app/environment/docs`, so the regenerated audits and the durable state around them are no longer correct or consistent. Bring the module behavior under `/app/environment` back onto the documented contract so the normal build-and-reload path produces conformant results: every matrix cell routed to its published backend target within the published row and group ceilings, refusal-marked cells left unrouted, byte-identical paired run digests, and the ledger, generations, registry, and the `status` and `verify` reports all consistent with one another. No outbound network access is available. Build the module and run each arm:

Required artifacts include: `/app/environment`, `/app/environment/docs`, `/app/environment/scripts/build_all.sh`, `/app/environment/bin/lb_drive`, `/app/output/haproxy_route_audit.json`, `/app/environment/docs/inv_fields.md`, `/app/environment/docs/rx_board.md`, `/app/environment/fixtures/qv/`.

Author anonymous tagged this **hard** system-administration task (haproxy, load-balancer, acl, sysadmin, go, bash).

Time estimates: expert ~240 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `0d35c7d1-a960-461c-ad58-1299f2e509cf_submission_2026-07-18T06_22_32.046Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
