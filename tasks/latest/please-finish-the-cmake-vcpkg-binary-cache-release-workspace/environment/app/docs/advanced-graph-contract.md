# Advanced graph contract

This document is normative and intentionally compact. It resolves graph rules
that must not be inferred from implementation details.

After profile and scope filtering, retain every active dependency source row in
`dependency_edges`. Sort rendered `parent->child:relation` strings but do not
deduplicate them. Every retained row contributes one `edge_count` and the usual
two risk points. Exact duplicates and parallel relations therefore remain
observable.

Ordering uses a different graph projection: create exactly one directed arc for
each unique `(parent, child)` pair. Duplicate rows and parallel relations never
multiply indegree. Compute strongly connected components (SCCs) over all
selected components and those unique arcs. A multi-node SCC is cyclic. A
one-node SCC is cyclic only when that component has an active self-loop.

Emit one sorted warning per cyclic SCC:

```text
dependency_cycle:<lexicographically sorted SCC names joined by |>
```

A cycle warning does not by itself fail `locked_versions`, although it makes
`policy_pass` false and contributes to warning risk. Never merge independent
SCCs, and never absorb an acyclic descendant of a cycle into its warning.

Collapse SCCs into the condensation DAG. Emit parent SCCs before child SCCs.
When multiple SCCs are ready, choose the SCC whose lexicographically smallest
member is smallest. Emit names inside an SCC lexicographically. These rules also
define ordering for disconnected roots, self-loops, and descendants released by
an emitted cyclic SCC.

Scope activation happens before graph projection. Empty scope and `all`,
`runtime`, `data`, `doc`, and `dev` are unconditional. Other simple scopes are
`&`-joined exact `feature:`, `target:`, and `channel:` clauses with optional `!`.
`cfg:` recursively supports `all`, `any`, and `not`. Unknown or malformed
expressions are inactive. Active non-optional edges from selected parents to
unselected children warn as documented; optional or inactive missing edges are
silent and create no graph arc.
