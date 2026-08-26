# Dependency closure contract

Edges in `dependencies.json` are objects `{ "from": "<decision_id>", "to": "<decision_id>" }` meaning `from` must complete before `to`.

## Cycle detection

If any directed cycle exists among decisions, set `cycle_detected` true, set `cycle_path` to the lexicographically smallest rotation of the cycle node list (sorted-start canonical form: rotate so the minimum id is first, then list the cycle without repeating the start at the end), mark the lattice and plan `feasible` false, and leave `execution_order` empty.

## Topological order

When acyclic, `execution_order` is a deterministic Kahn order: always pop the lexicographically smallest ready id from the zero-indegree set.
