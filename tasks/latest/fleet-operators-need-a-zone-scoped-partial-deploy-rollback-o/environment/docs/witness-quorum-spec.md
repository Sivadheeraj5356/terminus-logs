# Rollback witness quorum

Fleet zone apply gate for primary-host promotion. rollbackctl validate on the default bundled graph path writes /app/state/rollback-witness-bundle.json after plan-seal, inspect-manifest, and rollback-plan dependency checks succeed. validate must read egress-lane-midpipe.json midpipe_chain_digest for the witness row only. validate must not re-open wave-midpipe-snapshot.json or truth-ledger.json for witness sealing. Apply must refuse when the witness seal is missing or digests are tampered on the rollout path.

## rollback-witness-bundle.json

    {
      "capture_sequence": <integer>,
      "plan_hash": "<sha256>",
      "midpipe_chain_digest": "<sha256>",
      "zone_quorum_token": "<sha256>"
    }

capture_sequence must equal inspect-manifest.json capture_sequence from the active inspect run.

plan_hash must equal rollback-plan.json hash and plan-seal.json plan_hash.

midpipe_chain_digest must equal egress-lane-midpipe.json midpipe_chain_digest from the same plan emit run.

zone_quorum_token is SHA-256 hex over newline joined UTF-8 lines in this fixed order:

    incident|<incident_id>
    zone|primary
    chain|<midpipe_chain_digest>
    capture|<capture_sequence>
    plan|<plan_hash>

incident_id comes from deploy-status.json incident_id. zone is primary for bundled apply.

## apply cross-file checks

apply-rollback.sh must refuse when rollback-witness-bundle.json is missing, and otherwise must check exactly these four witness fields against the current pipeline run. No other witness field is compared, and the witness bundle is not re-checked against truth-ledger.json or wave-midpipe-snapshot.json:

    witness.capture_sequence      == inspect-manifest.json capture_sequence
    witness.plan_hash             == rollback-plan.json hash
    witness.midpipe_chain_digest  == egress-lane-midpipe.json midpipe_chain_digest
    witness.zone_quorum_token     == recomputed zone_quorum_token (fixed five-line order above)

The recomputed zone_quorum_token uses incident_id from deploy-status.json, zone primary, midpipe_chain_digest from egress-lane-midpipe.json, capture_sequence from inspect-manifest.json, and plan_hash from rollback-plan.json. All four checks read the state written by the current inspect, plan, and validate run, so a witness sealed in that run always matches. A plan emit without a subsequent validate leaves apply blocked even when egress-lane-midpipe.json exists.

rollbackctl plan and inspect must not write rollback-witness-bundle.json.

## zone priority inputs

/app/deploy/deploy-priority.json is not a zone quorum source and must not supply capture_sequence, plan_hash, midpipe_chain_digest, or zone_quorum_token.
