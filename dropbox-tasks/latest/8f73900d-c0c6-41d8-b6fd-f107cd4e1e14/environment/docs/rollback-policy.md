# Rollback policy

rollbackctl implements this workflow on the working /app baseline. Operators capture deploy truth, plan dependency-safe rollback waves, seal emits, and gate apply scripts. The bundled scenario below describes expected service outcomes for grading; implement the stages rather than restoring a pre-existing broken orchestrator.

## Partial deploy inspection

Authoritative deploy truth is /app/data/deploy/release-state.json

Rollback event logs under /app/data/logs/rollback-events.jsonl may be corrupted, delayed, or stale. inspect must prefer release-state.json over contradictory log lines. Delayed deploy_failed lines for identity-gate must not override release-state updated status.

After inspect, write /app/state/inspect-manifest.json with truth_source set to release-state, release_digest covering service|status lines from deploy-status.json in forward-order.json sequence, forward_digest binding forward-order.json, registry_release matching the incident registry release for incident_id, and capture_sequence matching the capture_sequence field in the truth-ledger midpipe file at /app/state/truth-ledger.json

inspect must also write /app/state/truth-ledger.json with capture_sequence (monotonic integer starting at 1 on first capture for an empty state directory) and incident_id from deploy-status.json. Each successful inspect increments capture_sequence when a prior ledger file exists.

plan must read truth-ledger.json and refuse when the file is missing or when capture_sequence disagrees with inspect-manifest.json before recomputing digests. Plan content hash line sequence is defined in wave-egress-schema.md. Egress-lane, topology-epoch latch, and run-ledger digest rules are in egress-lane-digest-spec.md and topology-epoch-latch.md.

/app/data/incident/registry.json maps each incident_id to release and failed_service strings. inspect-manifest registry_release must equal registry[incident_id].release for the active incident.

plan must recompute release_digest, forward_digest, and registry_release on every run and compare them to inspect-manifest before computing steps from deploy-status and rollback-graph. plan must exit non-zero when inspect-manifest is missing, truth_source is not release-state, or any recomputed digest or registry release disagrees with the manifest.

apply-rollback.sh validates /app/output/rollback-plan.json against plan-seal.json and rollback-graph dependencies. It does not read /app/deploy/rollback-order.json.

apply-rollback.sh must recompute release_digest from /app/state/deploy-status.json and compare it to inspect-manifest.json release_digest before writing /app/state/rollback-complete.ok containing ok.

Emit must write /app/state/plan-seal.json with plan_hash equal to the hash field embedded in rollback-plan.json. That hash is the content digest from release and step lines per wave-egress-schema.md (release line first, then lexicographically sorted step lines), not a file-byte digest. Seal must be rollback-bound. apply-rollback.sh must verify plan-seal.json plan_hash equals rollback-plan.json hash before writing rollback-complete.ok.

plan emit must also write /app/state/wave-midpipe-snapshot.json binding capture_sequence, plan_hash, and manifest_release_digest per wave-egress-schema.md, then /app/state/egress-lane-midpipe.json with wave_step_sequence_digest and midpipe_chain_digest per egress-lane-digest-spec.md. apply-rollback.sh must verify the snapshot, egress-lane chain, and rollback-run-ledger replay guard per egress-lane-digest-spec.md before writing rollback-complete.ok.

rollbackctl validate on the bundled topology checks plan-seal.json plan_hash against rollback-plan.json embedded hash, inspect-manifest release_digest against deploy-status.json service lines, and rollback step order against rollback-graph.json. validate must not read wave-midpipe-snapshot.json and must not compare truth-ledger.json capture_sequence. Those bindings belong to plan emit and apply-rollback.sh only. validate must read egress-lane-midpipe.json midpipe_chain_digest when sealing rollback-witness-bundle.json per witness-quorum-spec.md.

apply-rollback.sh sources validate-rollback-env.sh. ROLLBACK_INCIDENT_ID must match deploy-status.json incident_id. Wrong incident ids must exit non-zero.

## Service outcomes

| Service | Expected outcome |
|---------|------------------|
| ledger-db | updated |
| identity-gate | updated |
| billing-core | failed |
| alert-dispatch | updated |

Failed services are not rolled back. Updated services that deployed ahead of a downstream failure must be rolled back.

## Rollback sequence

Reverse dependency order for updated services only:

1. alert-dispatch
2. identity-gate
3. ledger-db

Never roll back ledger-db before identity-gate or billing-core paths.
