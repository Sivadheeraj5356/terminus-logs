`/app/src/sim.rs` runs at least 2000 operations, toggles partitions every 137 steps, and reconciles with `replicate_pair`. While connected, replicas mirror each other's inserts. During partitions each replica extends its own chain.

Sibling ordering rule: when multiple inserts target the same `after` anchor, traversal order is full `OpId` ascending (`replica_id`, then `counter`). The same rule applies in `materialize()` and `visible_op_ids()`.

When two concurrent inserts share the same `counter` on different replicas, `replica_id` breaks the tie.
