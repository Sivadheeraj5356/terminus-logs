# Fleet rollback derivation contract

Operators derive a dependent-first rollback wave from live deploy-status.json and rollback-graph.json, not from stale deploy ladder fixtures under /app/deploy.

Derivation path for graders:

1. Capture release truth into inspect-manifest.json and truth-ledger.json with matching capture_sequence.
2. Reverse only updated dependents for the plan steps using rollback-graph edges.
3. Seal plan hash from lexicographically sorted step lines after the release line.
4. Bind egress-lane midpipe_chain_digest and topology-epoch-latch graph freeze, then seal rollback-witness-bundle.json with the four quorum fields.
5. Apply writes rollback-run-ledger.json and refuses identical plan_hash plus capture_sequence replays.

Reasoning for this desk is cascade refuse on stale egress-lane digests, induction over the service edge walk, backtrack when graph cycles appear, prove of witness field parity, and deduce of apply replay from the run ledger. This path is zone-promotion ordered. It is not build-attest ledger closure and not supply-chain SBOM hashing.
