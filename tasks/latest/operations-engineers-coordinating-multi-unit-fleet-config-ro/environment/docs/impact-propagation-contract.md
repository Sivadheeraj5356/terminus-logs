# Impact propagation contract

Each decision lists `direct_units` (unit ids). Topology edges in `topology.json` are `{ "parent": "<unit>", "child": "<unit>" }` meaning impact on parent also reaches child.

## Fan-out

Affected units for a decision = transitive closure of `direct_units` following parent→child edges, including the direct units. Sort unit ids ascending in each impact_row.

## Impact score

`impact_score` for a decision equals the count of affected units after fan-out. Used by approval gates.
