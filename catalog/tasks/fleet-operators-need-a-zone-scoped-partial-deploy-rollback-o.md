# Fleet operators need a zone-scoped partial-deploy rollback orchestrator on the w

Submission: `8f73900d-c0c6-41d8-b6fd-f107cd4e1e14`  
Slug: `fleet-operators-need-a-zone-scoped-partial-deploy-rollback-o`  
Latest archive: `8f73900d-c0c6-41d8-b6fd-f107cd4e1e14_submission_2026-07-18T05_28_10.031Z.zip`  
Revisions in Dropbox: 4

## Task summary

Fleet operators need a zone-scoped partial-deploy rollback orchestrator on the working baseline under /app. Build it so rollbackctl at /app/bin/rollbackctl can capture release truth into midpipe under /app/state and publish a dependency-safe rollback wave at /app/output/rollback-plan.json with seal binding. It validates witness quorum for the primary zone and coordinates apply through /app/deploy/scripts/apply-rollback.sh when operators invoke it. The bundled incident in /app/data/deploy/release-state.json covers ledger-db, identity-gate, billing-core, and alert-dispatch for release rel-8821. Authoritative inputs are /app/data/deploy/forward-order.json, /app/data/topology/rollback-graph.json, and /app/data/incident/registry.json. Workflow and field contracts live in /app/docs/rollback-policy.md, /app/docs/dependency-graph.md, /app/docs/wave-egress-schema.md, /app/docs/egress-lane-digest-spec.md, /app/docs/topology-epoch-latch.md, /app/docs/witness-quorum-spec.md, and /app/docs/zone-apply-ops.md.

Required artifacts include: `/app/bin/rollbackctl`, `/app/state`, `/app/output/rollback-plan.json`, `/app/deploy/scripts/apply-rollback.sh`, `/app/data/deploy/release-state.json`, `/app/data/deploy/forward-order.json`, `/app/data/topology/rollback-graph.json`, `/app/data/incident/registry.json`.

Author anonymous tagged this **medium** system-administration task (fleet-rollout, topology-rollback, release-orchestration, zone-apply, go).

Time estimates: expert ~100 min, junior ~270 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8f73900d-c0c6-41d8-b6fd-f107cd4e1e14_submission_2026-07-18T05_28_10.031Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
