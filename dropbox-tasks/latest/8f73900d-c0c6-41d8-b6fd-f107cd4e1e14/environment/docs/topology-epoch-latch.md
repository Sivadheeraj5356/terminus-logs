# Topology epoch latch

Plan emit must write /app/state/topology-epoch-latch.json after egress-lane-midpipe.json. The latch freezes the live rollback-graph topology against the sealed plan so validate and apply cannot accept a wave after the graph drifts.

## Schema

    {
      "schema": "rollback.topology-epoch.v1",
      "capture_sequence": <integer>,
      "plan_hash": "<sha256>",
      "graph_epoch_digest": "<sha256>",
      "latch_digest": "<sha256>"
    }

capture_sequence must equal inspect-manifest.json capture_sequence from the same inspect run.

plan_hash must equal rollback-plan.json hash from the same plan emit.

## graph_epoch_digest

Read /app/data/topology/rollback-graph.json as a map of service name to dependency arrays. Emit one UTF-8 line per directed edge:

    dep|<service>|<dependency>

Sort services ascending, and within each service sort dependency names ascending. SHA-256 hex over the newline joined lines. An empty dependency list emits no lines for that service.

## latch_digest

SHA-256 hex over the single UTF-8 string:

    topo-latch|<capture_sequence>|<plan_hash>|<graph_epoch_digest>

with the three field values substituted (no extra spaces).

## validate and apply

rollbackctl validate on the bundled topology path must refuse when topology-epoch-latch.json is missing, when capture_sequence or plan_hash disagrees with live inspect-manifest and rollback-plan, or when graph_epoch_digest or latch_digest fails live recompute against the current rollback-graph.json and the stored capture_sequence and plan_hash. Validate must run this check before writing rollback-witness-bundle.json.

apply-rollback.sh must refuse when the latch is missing or fails the same live recompute before writing rollback-complete.ok.

A plan emit that omits the latch leaves validate and apply blocked even when egress-lane-midpipe.json and plan-seal.json exist. Mutating rollback-graph.json after plan without a fresh plan emit must fail validate.
