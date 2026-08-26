# Our offline-first editor at `/app` replicates text edits through an RGA sequence

- **UUID:** `2bdcc36d-dc9f-4ec3-bd26-27bdee0c46ba`
- **Slug:** `our-offline-first-editor-at-app-replicates-text-edits-throug`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Our offline-first editor at `/app` replicates text edits through an RGA sequence CRDT. Each replica maintains a Merkle DAG over its operation log with embedded vector clocks for diff-based anti-entropy, but partitioned replicas stop converging and concurrent inserts at the same anchor disagree on document order.

Bring `/app/src/merkle.rs`, `/app/src/sync.rs`, and `/app/src/sequence.rs` into compliance with `/app/spec/merkle_contract.md`, `/app/spec/sync_protocol.md`, and `/app/spec/sequence_crdt.md`. Compliance means the Merkle layer builds a balanced OpId-ordered tree with contract-correct hashing and minimal `diff_paths` (including the leaf-vs-internal shape case in the Merkle spec); sync helpers reconcile divergent DAGs via diff → export → import and deduplicate operation logs sorted by full `OpId`; and the sequence CRDT orders concurrent siblings and materializes documents by full `OpId`, not counter alone.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
