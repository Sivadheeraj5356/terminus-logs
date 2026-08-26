# Public invariants

These phrases are the public allowance and schema anchors. Full arithmetic lives
in `/app/environment/docs/contract.rst`. Durable store layout lives in
`/app/environment/docs/protocol.rst`. Input and plan schemas live in
`/app/environment/docs/input-format.rst` and `/app/environment/docs/plan-format.rst`.

Allowance for a rung is budget * n where n is the rung row count. A family is
feasible on that rung only when its sealed-edge deviation is at most that
allowance.

Bundle fields include unit, bins, cells, lanes, fit, rim, hold, and rungs. Plan
fields include unit, bins, hold, and rungs. Rung records include severity,
family, strength, deviation, allowance, and values. Family names are hist, iso,
and giso. Row fields include raw, hit, and lane. Each rung may carry budget and
span.

The fold digest is a sixteen-character hex string (16 hex digits). Resume floors
use strengths 0, 1, and 2.
