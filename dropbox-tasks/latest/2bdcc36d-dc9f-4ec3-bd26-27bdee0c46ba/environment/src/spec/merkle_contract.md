# Merkle DAG Contract

Each replica keeps a Merkle DAG over its operation log in `/app/src/merkle.rs`.

## Invariants

- Operations are sorted by full `OpId` ascending (`replica_id`, then `counter`) and placed in a **balanced binary tree** keyed by that order.
- Root path is `""`; children append `L` or `R`.
- Leaves store one operation and the vector clock observed at ingest time.
- Internal nodes store the merged subtree clock and a SHA-256 digest.
- Identical operation logs on different replicas must yield identical `root_hash()` values regardless of the local `replica_id` field on the DAG struct.

## Hashing

Leaf: `SHA256(operation.canonical_bytes() || clock.canonical_bytes())`

Internal: `SHA256(left.hash || right.hash || merged_clock.canonical_bytes())`

Empty DAG root: `SHA256(b"MERKLE-CRDT-EMPTY")`

## Diff

`diff_paths(remote)` must return the **minimal** set of subtree paths whose digests differ. When roots match, return an empty list. When a leaf exists on only one side, that path must appear. Do not return ancestor paths when only a descendant differs.

### Shape mismatch examples

`diff_paths` is symmetric in call direction but not in tree shape. Both directions must recurse past a mismatched root when one side is a leaf and the other is internal.

**`local.diff_paths(&remote)` — local leaf, remote internal:** Local holds one operation, so path `""` is a **leaf** storing that op. Remote holds two operations, so path `""` is an **internal** node with children at `L` and `R`. Root hashes differ, but exporting only `""` cannot transfer remote leaves. The diff must recurse into `L` and/or `R` and return those descendant paths—not stop at the root alone.

**`remote.diff_paths(&local)` — remote internal, local leaf:** Same logs as above, but `self` is the two-operation replica and the argument is the one-operation replica. Path `""` is internal on `self` and a leaf on the argument. The diff must still descend into child paths (for example `L` or `R`) rather than returning only `""`, because the missing operation lives under a child subtree.

## API (`/app/src/merkle.rs`)

Implement `ingest`, `root_hash`, `node_clock`, `subtree_hash`, `export_node`, `import_node`, and `diff_paths`. Invalid paths return `MerkleError::InvalidPath`.

## Harness

```bash
cd /app && cargo build --release --bin scenetest
/app/bin/scenetest --scenario m1_merkle_dag --seed 42
```

Do not modify `/app/src/bin/scenetest`, `/app/src/sim.rs`, or files under `/app/spec`.
