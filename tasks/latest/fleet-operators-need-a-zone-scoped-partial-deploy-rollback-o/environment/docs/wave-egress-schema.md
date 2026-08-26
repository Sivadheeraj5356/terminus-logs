# Wave emit schema

## inspect-manifest.json

Written by inspect to /app/state/inspect-manifest.json:

    {
      "truth_source": "release-state",
      "release_digest": "<sha256>",
      "forward_digest": "<sha256>",
      "registry_release": "<release_id>",
      "capture_sequence": <integer>
    }

capture_sequence must equal truth-ledger.json capture_sequence written during the same inspect run.

## truth-ledger.json

Written by inspect to /app/state/truth-ledger.json:

    {"capture_sequence": <integer>, "incident_id": "<incident_id>"}

First inspect in a clean state directory uses capture_sequence 1. Later inspect runs increment the prior value.

plan and emit must read truth-ledger.json, refuse when it is missing, and compare capture_sequence to inspect-manifest.json before digest recomputation.

apply-rollback.sh must verify truth-ledger.json exists and capture_sequence matches inspect-manifest.json before writing rollback-complete.ok.

release_digest covers service|status lines from deploy-status.json in forward-order.json sequence (one line per service listed in forward-order, skipping services absent from deploy-status). Do not sort digest lines lexicographically before sha256.

Compute release_digest and forward_digest from live deploy-status.json and forward-order.json using the rules above. Do not sort release_digest service lines lexicographically.

registry_release must match /app/data/incident/registry.json release for the active incident_id.

## plan manifest verification

plan and emit must read /app/state/inspect-manifest.json before computing steps. Refuse when the file is missing or truth_source is not release-state.

On every plan run, recompute and compare:

1. release_digest — read /app/data/deploy/forward-order.json, emit service|status lines in that array order from /app/state/deploy-status.json, SHA-256 hex newline joined without sorting, must equal manifest release_digest.
2. forward_digest — read /app/data/deploy/forward-order.json, SHA-256 hex over newline joined service names, must equal manifest forward_digest.
3. registry_release — load /app/data/incident/registry.json, look up deploy-status incident_id, compare registry[incident_id].release to manifest registry_release.

Only after all three checks pass, compute steps from deploy-status.json and rollback-graph.json. Never build the plan from /app/deploy/rollback-order.json or /app/deploy/deploy-priority.json.

## poison and decoy files

/app/deploy/rollback-order.json is a stale forward-deploy artifact (wrong sequence, includes failed billing-core). It is not an apply manifest. rollbackctl plan, rollbackctl validate, and apply-rollback.sh must ignore it.

/app/deploy/deploy-priority.json is not an authoritative input for plan order, plan hash lines, or apply. Use deploy-status.json and rollback-graph.json only.

## rollback-plan.json

    {"steps": ["alert-dispatch", "identity-gate", "ledger-db"], "release": "rel-8821", "hash": "<sha256>"}

billing-core must not appear when its deploy status is failed.

Hash is SHA-256 hex of newline-joined UTF-8 lines. Emit the release line first, then one step line per rollback service sorted lexicographically by service name (same rule as Python hashlib.sha256 over newline-joined bytes):

    release|<release_id>
    step|<service>   (sorted)

Example for release rel-8821 and steps alert-dispatch, identity-gate, ledger-db:

    release|rel-8821
    step|alert-dispatch
    step|identity-gate
    step|ledger-db

## validate-rollback-env

apply-rollback.sh sources /app/scripts/validate-rollback-env.sh. ROLLBACK_INCIDENT_ID must be set and must equal the incident_id field in /app/state/deploy-status.json for the active rollback (inc-4429 for bundled data). A wrong but present incident id must be rejected the same as a missing variable. ROLLBACK_ZONE must be primary during apply.

## plan-seal.json

Written by plan emit to /app/state/plan-seal.json:

    {"plan_hash": "<sha256>", "seal": "rollback-bound"}

plan_hash must equal the hash string field embedded inside /app/output/rollback-plan.json (the content digest computed from step and release lines in this schema). It is not a digest of the rollback-plan.json file bytes on disk.

apply-rollback.sh and rollbackctl validate must compare plan-seal.json plan_hash to rollback-plan.json hash before accepting apply or validate success.

## rollbackctl validate scope

rollbackctl validate on the default bundled graph path performs these checks only:

1. plan-seal.json plan_hash equals rollback-plan.json hash and seal is rollback-bound
2. inspect-manifest.json release_digest equals a digest recomputed from deploy-status.json service|status lines in forward-order.json sequence
3. rollback-plan.json steps satisfy rollback-graph.json dependency order
4. writes rollback-witness-bundle.json per witness-quorum-spec.md using egress-lane-midpipe.json midpipe_chain_digest

validate must not open wave-midpipe-snapshot.json. validate must not read truth-ledger.json or compare capture_sequence fields except through witness bundle fields copied from inspect-manifest and egress-lane. Snapshot and ledger sequence alignment is enforced by plan emit and apply-rollback.sh, not by validate plan binding checks.

rollbackctl validate --graph PATH checks cycle freedom on an arbitrary graph file only and skips plan binding checks.

## wave-midpipe-snapshot.json

Written by plan emit to /app/state/wave-midpipe-snapshot.json after plan-seal.json:

    {
      "capture_sequence": <integer>,
      "plan_hash": "<sha256>",
      "manifest_release_digest": "<sha256>"
    }

capture_sequence must equal inspect-manifest.json capture_sequence and truth-ledger.json capture_sequence from the same inspect run.

plan_hash must equal rollback-plan.json hash and plan-seal.json plan_hash.

manifest_release_digest must equal inspect-manifest.json release_digest.

apply-rollback.sh must refuse when wave-midpipe-snapshot.json is missing or when any snapshot field disagrees with live inspect-manifest, rollback-plan, or truth-ledger artifacts. A second inspect that increments capture_sequence without a fresh plan emit leaves a stale snapshot that must block apply.

Egress-lane midpipe, wave_step_sequence_digest, midpipe_chain_digest, and rollback-run-ledger replay rules are in egress-lane-digest-spec.md.
