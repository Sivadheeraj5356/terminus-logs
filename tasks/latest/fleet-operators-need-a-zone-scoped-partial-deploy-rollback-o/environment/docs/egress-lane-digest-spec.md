# Egress lane and apply ledger digests

This document defines egress-lane-midpipe.json, midpipe_chain_digest, wave_step_sequence_digest, and rollback-run-ledger.json. Plan emit write order is in wave-egress-schema.md.

## Plan emit write order

Plan emit must write midpipe artifacts in this order only:

1. rollback-plan.json under /app/output
2. plan-seal.json under /app/state
3. wave-midpipe-snapshot.json under /app/state
4. egress-lane-midpipe.json under /app/state
5. topology-epoch-latch.json under /app/state per topology-epoch-latch.md

Each later file must bind fields from earlier artifacts in the same emit run. apply-rollback.sh verifies the full chain. rollbackctl validate must not read wave-midpipe-snapshot.json or truth-ledger.json. Validate must read topology-epoch-latch.json per topology-epoch-latch.md and egress-lane-midpipe.json midpipe_chain_digest per witness-quorum-spec.md before sealing the witness bundle.

## egress-lane-midpipe.json

Written by plan emit to /app/state/egress-lane-midpipe.json after wave-midpipe-snapshot.json:

    {
      "capture_sequence": <integer>,
      "plan_hash": "<sha256>",
      "wave_step_sequence_digest": "<sha256>",
      "midpipe_chain_digest": "<sha256>"
    }

capture_sequence must equal inspect-manifest.json capture_sequence from the same inspect run.

plan_hash must equal rollback-plan.json hash, plan-seal.json plan_hash, and wave-midpipe-snapshot.json plan_hash.

wave_step_sequence_digest binds rollback execution order (array order from rollback-plan.json steps, not lexicographic sort). SHA-256 hex over newline joined UTF-8 lines:

    wave|<index>|<service>

Index starts at 0 for the first step in the plan steps array. Example for steps alert-dispatch, identity-gate, ledger-db:

    wave|0|alert-dispatch
    wave|1|identity-gate
    wave|2|ledger-db

Do not use lane|step| prefixes or lexicographic step sorting for this digest.

midpipe_chain_digest binds capture_sequence, plan_hash, manifest release_digest from wave-midpipe-snapshot.json, and wave_step_sequence_digest from the same egress-lane row. SHA-256 hex over newline joined UTF-8 lines in this fixed order:

    capture|<capture_sequence>
    plan|<plan_hash>
    release|<manifest_release_digest>
    wave|<wave_step_sequence_digest>

manifest_release_digest in the chain line must equal inspect-manifest.json release_digest and wave-midpipe-snapshot.json manifest_release_digest from the same inspect run.

rollbackctl validate must read egress-lane-midpipe.json midpipe_chain_digest when sealing rollback-witness-bundle.json per witness-quorum-spec.md. validate must not recompute or re-verify wave_step_sequence_digest against the plan steps array during that seal, and must not open wave-midpipe-snapshot.json for the witness row. apply-rollback.sh must verify egress-lane-midpipe.json exists and all four fields match live inspect-manifest, rollback-plan, wave-midpipe-snapshot, and recomputed wave_step_sequence_digest and midpipe_chain_digest before writing rollback-complete.ok.

## rollback-run-ledger.json

Written by apply-rollback.sh to /app/state/rollback-run-ledger.json after a successful apply:

    {
      "apply_epoch": <integer>,
      "last_plan_hash": "<sha256>",
      "last_capture_sequence": <integer>
    }

apply_epoch starts at 1 on first successful apply and increments on each later successful apply for the same capture_sequence and plan_hash pair.

apply-rollback.sh must refuse when rollback-run-ledger.json already records the same last_plan_hash and last_capture_sequence as the current rollback-plan hash and inspect-manifest capture_sequence (replay without a fresh inspect and plan emit). A fresh inspect that bumps capture_sequence followed by plan emit clears the replay guard because last_capture_sequence no longer matches.

rollbackctl plan and validate must not read rollback-run-ledger.json.
