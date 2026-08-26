# Blend ledger contract

## Output path

/app/output/blend-ledger.json

## Entry order

Ledger entries follow the specification order stored in blend-model.json after bind sorting:

1. ascending priority (lower priority number first)
2. ascending spec_id tie-break

For bundled fixtures this order is SPEC-01, SPEC-02, SPEC-03.

## Entry fields

Each entry contains spec_id, priority, feasible, total_cost, and lot_amounts_ml mirroring the allocation solution row without concentrations.

solve writes the ledger from persisted blend-model only. Mutating /app/input after bind must not change ledger content on a subsequent solve.
