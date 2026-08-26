# Dependency graph

Read /app/data/topology/rollback-graph.json for deploy edges.

Forward deploy order is recorded in /app/data/deploy/forward-order.json — rollback reverses dependents first among updated services.

Deploy edges (service depends on):

- identity-gate → ledger-db
- billing-core → identity-gate, ledger-db
- alert-dispatch → billing-core

Rollback walks dependents first: alert-dispatch before identity-gate before ledger-db.

## Circular dependencies

rollbackctl validate must reject graphs containing cycles. Every graph node listed in rollback-graph.json participates in cycle detection with no node excluded from the walk, including alert-dispatch, billing-core, identity-gate, and ledger-db when present. Skipping any listed node during the cycle walk is incorrect. Use rollbackctl validate --graph /path/to/graph.json to check arbitrary graph files. Cycle rejection alone does not replace a correct plan emit under wave-egress-schema.md and the incident registry contracts.
