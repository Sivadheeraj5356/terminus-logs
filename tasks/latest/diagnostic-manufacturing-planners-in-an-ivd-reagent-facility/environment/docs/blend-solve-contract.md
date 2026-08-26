# Blend solve contract

## Blend model (bind output)

/app/state/blend-model.json schema_version blend-model/1 fields:

- batch_generation: copied from lots.json batch_generation
- target_volume_ml: copied from lots.json
- lots: deep copy of lots array with full-precision assay values from lots.json
- specifications: sorted by ascending priority then ascending spec_id
- source_lots and source_specs: absolute input paths

## Allocation (solve state output)

/app/state/allocation.json schema_version allocation/1 fields:

- batch_generation, target_volume_ml from model
- solutions: one row per specification in model order with spec_id, priority, feasible, total_cost, lot_amounts_ml, concentrations

When feasible is false, total_cost is 0.0 and lot_amounts_ml and concentrations are empty objects.

## Blend ledger (solve public output)

/app/output/blend-ledger.json schema_version blend-ledger/1 fields:

- batch_generation from model
- entries: one row per specification with spec_id, priority, feasible, total_cost, lot_amounts_ml (no concentrations field)

## Lot inventory ledger

bind also writes /app/state/lot-inventory.json per lot-inventory-contract.md.

solve must treat remaining_ml from lot-inventory as the effective available_ml cap for each lot while solving specifications in model order. After each feasible allocation, debit lot_amounts_ml from remaining_ml and persist the updated lot-inventory.json before advancing to the next specification. Specifications do not share a single simultaneous LP; later specifications see depleted remaining_ml from earlier feasible blends.

## Solve algorithm

BlendSolve enumerates volume fractions on a grid with STEPS=101 per lot, respecting the effective available_ml caps from lot-inventory, and picks the minimum total_cost feasible blend per specification.

### Grid fraction rule (STEPS=101)

Use integer tick counts fracs[i] from 0 through STEPS inclusive. The lot amount for tick fracs[i] is:

  amount_ml[i] = (fracs[i] / STEPS) * target_volume_ml

Do not use (STEPS - 1) in the denominator. For example, when STEPS is 101, the smallest positive step is target_volume_ml / 101, not target_volume_ml / 100.

Depth-first enumeration assigns ticks per lot so the partial sum of assigned ticks never exceeds STEPS; the final lot receives STEPS minus the sum of prior ticks.
