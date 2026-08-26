# Lot inventory ledger contract

## Path

/app/state/lot-inventory.json

## Schema lot-inventory/1

- batch_generation: copied from lots.json batch_generation
- lots: array of {lot_id, remaining_ml} in the same order as lots.json

bind writes the initial snapshot from lots.json available_ml values.

## Solve consumption

solve reads blend-model.json and lot-inventory.json only. For each specification in model order, solve uses remaining_ml from lot-inventory as the available_ml cap when running BlendSolve. After a feasible allocation, subtract each positive lot_amounts_ml from the matching remaining_ml and rewrite lot-inventory.json before the next specification.

certify and seal must not read lot-inventory.json.

## Exit codes (input vs state)

Missing or unreadable files under /app/input during bind are bad input and exit 3.

Missing /app/state artifacts required by solve, certify, or seal (including lot-inventory.json after bind) are missing state and exit 2.
