# Diff-Based Sync Protocol

Implement anti-entropy in `/app/src/sync.rs` once `/app/src/merkle.rs` produces consistent roots.

## Invariants

- `diff_paths(remote)` returns the minimal set of subtree paths whose digests differ; an empty list when roots match.
- When a leaf exists on only one side, that path must appear in the diff.
- When the same path is a leaf on one side and an internal node on the other, recurse into child paths in both call directions (see the shape-mismatch examples in `/app/spec/merkle_contract.md`).
- `collect_exports` / `apply_exports` round-trip `MerkleExport` values without corrupting unrelated subtrees.
- `anti_entropy(local, remote)` reconciles DAG state via diff → export from remote → import into local.
- `merge_operation_log` deduplicates by `OpId`, preserves one `(Operation, VectorClock)` per id, and sorts by full `OpId` ascending (`replica_id`, then `counter`).

`replicate_pair` in `/app/src/sim.rs` depends on these helpers. After syncing, replicas must share identical Merkle roots and materialized documents.

## Scenarios

`m1_merkle_dag`, `m1_cross_replica_root`, `m2_diff_sync`, `m2_concurrent_fork`, `m2_interleaved_branches`, `m2_delete_resync`, `m3_partition_stress`

Do not modify `/app/src/bin/scenetest`, `/app/src/sim.rs`, or files under `/app/spec`.
