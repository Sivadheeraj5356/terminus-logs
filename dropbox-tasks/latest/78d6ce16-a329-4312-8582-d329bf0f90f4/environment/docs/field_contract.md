# Unity Ink Field Contract

The pending settlement feed is ordered by clearing sequence. Reconciliation
must preserve that order in the emitted report so downstream wire-control
systems can match rows without another join pass.

The `settlement_id` column is an opaque batch-local identifier. The
`amount_decimal` column is a non-negative base-10 integer serialized without
currency punctuation. The `radix_base` column selects the UNITY-47 rail radix
used by the member bank for that settlement.

The report repeats those three public fields and appends `min_ink`, the
denomination weight defined by the rail specification.
